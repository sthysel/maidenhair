# WebGL Client-Side Rendering Plan

## Goal

Move 3D rendering from the server (moderngl subprocess) to the browser (three.js
WebGL), so camera interaction is instant regardless of network latency. The server
only sends geometry data when the L-system changes.

---

## Current Architecture

```
Browser (flet Flutter Web)              Server (Python)
  ft.Image displays JPEG bytes  <----  moderngl renders per frame
  mouse events sent per drag    ---->  viewport.rotate()/zoom()
  ~60ms round-trip per frame           render() called 30x/sec
```

Every mouse drag is a network round-trip. Frame rate is limited by latency.

## Target Architecture

```
Browser                                  Server (Python)
  three.js renders locally at 60fps      core/ produces Geometry
  OrbitControls handles camera locally   sends geometry JSON on change
  no per-frame network traffic           only on preset/param/iteration change
```

Camera interaction is fully client-side. Server only involved when the L-system
needs recomputation.

---

## Scope

### What changes
- `ui/canvas.py` — new `WebGLCanvas` class for web mode (alongside existing `LSystemCanvas`)
- `core/turtle3d.py` — add `Geometry.to_dict()` serialisation method
- New `static/viewer.js` — three.js WebGL viewer (~150 lines)
- New `static/viewer.html` — minimal HTML wrapper

### What doesn't change
- `core/grammar.py`, `core/parametric.py`, `core/presets.py`, `core/palette.py`
- `render/viewport.py`, `render/gl_viewport.py`, `render/gl_process.py` (still used for CLI and desktop)
- `render/mesh.py`, `render/export.py` (still used for OBJ/GLB/PLY export)
- `ui/sidebar.py`, `ui/toolbar.py`, `ui/app.py`
- All presets, tests
- CLI commands

---

## Implementation Steps

### Step 1: Geometry Serialisation

Add a method to `Geometry` that converts segments and leaves to a plain dict
suitable for JSON serialisation.

**File: `src/maidenhair/core/turtle3d.py`**

```python
def to_dict(self) -> dict:
    """Serialise geometry for client-side rendering."""
    return {
        "segments": [
            {
                "start": start.tolist(),
                "end": end.tolist(),
                "radius": float(radius),
            }
            for start, end, radius in self.segments
        ],
        "leaves": [
            {
                "position": pos.tolist(),
                "heading": heading.tolist(),
                "left": left.tolist(),
            }
            for pos, heading, left in self.leaves
        ],
    }
```

For large geometries (>10k segments), consider a binary format (MessagePack or
a flat Float32Array) instead of JSON to reduce transfer size and parse time.

### Step 2: three.js Viewer

A self-contained JS module that:

1. Receives geometry data (segments + leaves) as a JSON object
2. Builds `THREE.BufferGeometry` for branches (thick lines or instanced quads)
3. Builds leaf geometry as oriented fan-shaped triangles
4. Sets up `OrbitControls` for camera interaction
5. Renders at browser-native refresh rate (typically 60fps)
6. Exposes a `updateGeometry(data)` function for Python to call
7. Exposes a `setColors(branch, leaf, background)` function

**File: `src/maidenhair/static/viewer.js`**

Key three.js components:
- `THREE.WebGLRenderer` with antialiasing
- `THREE.PerspectiveCamera` with auto-fit to bounding box
- `OrbitControls` from three/addons (handles drag-to-orbit, scroll-to-zoom, right-drag-to-pan)
- `THREE.InstancedMesh` or `THREE.LineSegments2` (from three/addons/lines) for
  thick branches with varying width
- Custom `THREE.BufferGeometry` for fan-shaped leaves
- `THREE.Fog` for depth shading

three.js can be loaded from a CDN (`unpkg.com/three`) or bundled.

**File: `src/maidenhair/static/viewer.html`**

```html
<!DOCTYPE html>
<html>
<head><style>body { margin: 0; overflow: hidden; }</style></head>
<body>
<script type="importmap">
{
  "imports": {
    "three": "https://unpkg.com/three@0.170/build/three.module.js",
    "three/addons/": "https://unpkg.com/three@0.170/examples/jsm/"
  }
}
</script>
<script type="module" src="viewer.js"></script>
</body>
</html>
```

### Step 3: Flet Integration

Embed the three.js viewer inside flet using one of these approaches (in order of
preference):

#### Option A: flet's JavaScript bridge (`page.js`)

Flet 0.82 may support running JavaScript in the browser context. If so, inject
the three.js viewer directly into the page DOM and communicate via `page.js.call()`.

```python
# Python side
await page.js.call("updateGeometry", geometry.to_dict())
```

This is the cleanest integration — no iframe, no postMessage.

#### Option B: WebView / iframe

Serve `viewer.html` as a static asset. Embed it in an iframe via flet's
`ft.WebView` control or a raw HTML container. Communicate via `postMessage`:

```python
# Python side — send geometry to iframe
import json
js = f"document.getElementById('viewer').contentWindow.postMessage({json.dumps(geo_dict)}, '*')"
page.run_javascript(js)
```

```javascript
// viewer.js — receive geometry
window.addEventListener('message', (e) => updateGeometry(e.data));
```

#### Option C: Custom flet extension

Write a `@ft.control("webgl_viewer")` backed by a Dart widget that wraps an
`HtmlElementView` (on web) containing the three.js canvas. This gives the
tightest integration but requires Dart code.

### Step 4: Canvas Mode Detection

Update `ui/canvas.py` to detect whether the app is running in web mode and
choose the appropriate rendering strategy.

**File: `src/maidenhair/ui/canvas.py`**

```python
def _is_web_mode(page: ft.Page) -> bool:
    """Check if running in browser."""
    return page.web  # flet provides this flag

class LSystemCanvas(ft.Container):
    def __init__(self):
        if _is_web_mode():
            # WebGL mode: embed three.js viewer, send geometry on change
            self._web_viewer = ...
        else:
            # Desktop mode: existing moderngl subprocess pipeline
            self.viewport = _create_viewport()
```

In web mode:
- `recompute()` sends geometry JSON to the JS viewer instead of rendering an image
- `rotate()`, `zoom()`, `pan()` are not called — OrbitControls handles them client-side
- `_render_frame()` is not called — three.js renders continuously
- `_on_pan_update`, `_on_scroll` are not wired to the GestureDetector

### Step 5: Static Asset Serving

Flet serves static files from an `assets/` directory. Place the viewer files there:

```
src/maidenhair/
├── assets/
│   ├── viewer.html
│   └── viewer.js
```

Configure in flet:
```python
ft.app(target=_app, assets_dir="assets")
```

---

## Data Flow Comparison

### Desktop (unchanged)
```
Preset change -> LSystem.derive() -> tokenise() -> interpret() -> Geometry
  -> GLProcessViewport.set_geometry() -> moderngl renders
  -> JPEG bytes -> ft.Image.src = bytes
Mouse drag -> viewport.rotate() -> render() -> ft.Image update
```

### Web (new)
```
Preset change -> LSystem.derive() -> tokenise() -> interpret() -> Geometry
  -> geometry.to_dict() -> JSON -> postMessage/js.call -> three.js updateGeometry()
  -> three.js rebuilds BufferGeometry -> renders at 60fps
Mouse drag -> OrbitControls (browser-local, no server contact)
```

---

## Performance Expectations

| Metric | Desktop (current) | Web (server-render) | Web (WebGL client) |
|--------|-------------------|--------------------|--------------------|
| Camera rotation FPS | 30 | 5-15 (latency-bound) | 60 (native) |
| Recompute latency | ~50ms | ~50ms + network | ~50ms + network + JSON parse |
| Bandwidth during rotation | 0 | ~1.5 MB/s | 0 |
| Bandwidth on recompute | 0 | 0 | ~50-500 KB (geometry JSON, once) |
| GPU memory | Server GPU | Server GPU | Client GPU |
| Server cost per user | 1 GL context | 1 GL context | CPU only |

---

## Dependencies

New (browser-side only, loaded from CDN):
- `three.js` (~150KB gzipped) — 3D rendering
- `OrbitControls` (included with three.js addons) — camera interaction

No new Python dependencies.

---

## Risk / Open Questions

1. **flet JS bridge**: Need to verify that `page.js.call()` or `page.run_javascript()`
   works in flet 0.82 web mode. If not, fall back to the iframe approach.

2. **three.js line width**: WebGL has the same 1px line width limitation on some
   browsers. Use `Line2` / `LineMaterial` from three.js addons for thick lines,
   or use instanced cylinder meshes (same approach as our moderngl quads).

3. **Large geometry transfer**: At iteration 8+ with 100k segments, the JSON
   geometry could be 5-10 MB. Consider binary transfer (ArrayBuffer) or
   server-side decimation for the web view.

4. **Hybrid mode**: Users may want to run the desktop app locally but access it
   via browser on the same machine (`flet run --web`). In this case the WebGL
   approach is overkill since latency is ~0. Could auto-detect and use the
   image pipeline for localhost, WebGL for remote.

5. **Export**: The three.js viewer would need its own "Export PNG" button that
   calls `renderer.domElement.toDataURL()` for screenshots. Mesh export (OBJ/GLB)
   still goes through the server since trimesh runs in Python.

---

## Estimated Effort

| Task | Effort |
|------|--------|
| Geometry serialisation (`to_dict()`) | 30 min |
| three.js viewer (viewer.js + viewer.html) | 3-4 hours |
| Flet integration (canvas.py web mode) | 2-3 hours |
| Testing across browsers (Chrome, Firefox) | 1-2 hours |
| **Total** | **~1 day** |

No changes needed to core/, presets, CLI, tests, sidebar, or toolbar.

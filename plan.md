# Maidenhair — L-System Botanical Explorer

## Goal

A cross-platform desktop/web application for interactively exploring parametric L-system plant
models, with real-time 3D visualisation and export to standard 3D formats. Built on a modern
Python stack using `uv` and `flet`.

---

## Coordinate System

**Y-up, right-handed.** The turtle starts at the origin facing +Y (upward growth). Gravity
points in the **-Y** direction. The camera default looks down the -Z axis toward the origin.

All code in `core/`, `render/`, and `ui/` must use this convention consistently.

---

## Stack

| Concern                    | Package                 | Rationale                                                        |
|----------------------------|-------------------------|------------------------------------------------------------------|
| UI / platform              | `flet`                  | Flutter-backed, runs desktop, web, and mobile from one codebase  |
| Package management         | `uv` + `pyproject.toml` | Standard modern tooling, lockfile included                       |
| Numerics                   | `numpy`                 | Turtle geometry, transformation matrices                         |
| 3D geometry / export       | `trimesh`               | Mesh construction, OBJ/GLB/PLY export, no heavy deps             |
| Image compositing          | `pillow`                | Offscreen rasterisation for the Flet viewport                    |
| Task runner                | `just`                  | Standard `justfile` with `dev`, `run`, `build`, `export` recipes |
| CLI                        | `typer`                 | Headless render and batch export                                 |
| Logging                    | `rich`                  | Progress bars during derivation                                  |
| TOML parsing               | `tomllib` (stdlib)      | Python 3.13 ships it — no third-party `toml` package needed      |
| Software quality assurance | pytest, ty, pre-commit  |                                                                  |


No `conda`. No `L-Py`. No `PlantGL`. Entirely pip-installable.

---

## Repository Layout

```
maidenhair/
├── pyproject.toml
├── .python-version          # 3.13
├── .pre-commit-config.yaml
├── .envrc                   # direnv: activate venv, install pre-commit
├── .secrets.baseline
├── uv.lock
├── justfile
├── README.md
└── src/
    └── maidenhair/
        ├── __init__.py
        ├── __main__.py          # python -m maidenhair support
        ├── core/
        │   ├── grammar.py       # String rewriting engine
        │   ├── parametric.py    # Parametric symbol parser
        │   ├── turtle3d.py      # 3D turtle → raw geometry
        │   └── presets.py       # Load/validate TOML presets
        ├── presets/             # TOML botanical grammar files (package data)
        │   ├── adiantum.toml
        │   ├── monopodial_tree.toml
        │   └── sympodial_tree.toml
        ├── render/
        │   ├── viewport.py      # numpy software rasteriser → PIL image
        │   ├── mesh.py          # trimesh cylinder/cone mesh builder
        │   └── export.py        # OBJ / GLB / PLY writer
        ├── ui/
        │   ├── app.py           # flet.app() entry point
        │   ├── canvas.py        # Flet Image control wrapping the viewport
        │   ├── sidebar.py       # Parameter sliders and preset selector
        │   └── toolbar.py       # Export, reset, iteration controls
        └── cli.py               # typer CLI for headless use
```

Presets live inside the package (`src/maidenhair/presets/`) so they are discoverable after
`pip install` via `importlib.resources`. They are **not** at the repo root.

---

## Core Architecture

### 1. Grammar engine (`core/grammar.py`)

Implement a clean, tested `LSystem` dataclass. Keep it pure — no side effects, no global state.

```python
@dataclass
class LSystem:
    axiom: str
    rules: dict[str, str]               # simple productions
    stochastic: dict[str, list[tuple[float, str]]] = field(default_factory=dict)
    max_string_length: int = 50_000_000  # safety limit (~50 MB)
    # context-sensitive rules deferred to v2

    def derive(self, n: int, *, seed: int | None = None) -> str:
        """Return the nth derivation string.

        If seed is given, use it for stochastic rule selection (reproducible).
        Raises ValueError if the derivation string exceeds max_string_length.
        """

    def derive_iter(self, n: int, *, seed: int | None = None) -> Iterator[str]:
        """Yield each generation string. Useful for progress reporting."""
```

Rules are plain `dict[str, str]` for deterministic grammars. Stochastic alternatives are a list
of `(weight, successor)` tuples — normalise weights internally, don't require them to sum to 1.

The `seed` parameter controls stochastic rule selection. Pass `None` for a random seed, or a
specific int for reproducibility. The UI's "Randomise stochastic" button generates a new random
seed and re-derives.

The `max_string_length` guard prevents runaway memory usage at high iteration counts. Some
grammars exceed 100 MB by iteration 7. Raise `ValueError` with a clear message when exceeded.

### 2. Parametric symbol support (`core/parametric.py`)

Support symbols with numeric parameters: `F(2.5)`, `+(30)`, `!(0.8)`. The parser should
tokenise a derivation string into a list of `Symbol(name: str, params: list[float])` objects.
Production rules that need parametric behaviour are expressed as callables:

```python
rules = {
    "F": lambda params: f"F({params[0]*0.9})[-F({params[0]*0.7})]F({params[0]*0.9})"
}
```

Keep a non-parametric fast path — don't pay the parsing cost for simple string grammars.

**Important**: parametric parsing is needed from the start — the bundled presets already use
parametric syntax like `+(48)` in their rules. The turtle interpreter depends on this module to
interpret any preset correctly.

### 3. 3D Turtle interpreter (`core/turtle3d.py`)

Produce a `Geometry` dataclass containing:

- `segments: list[tuple[np.ndarray, np.ndarray, float]]` — (start, end, radius) for each drawn segment
- `leaves: list[tuple[np.ndarray, np.ndarray]]` — (position, normal) for terminal surfaces

Standard turtle symbol set:

| Symbol            | Action                                              |
|-------------------|-----------------------------------------------------|
| `F(l)`            | Move forward `l`, emit segment                      |
| `f(l)`            | Move forward `l`, no segment (petiole)              |
| `+(a)` / `-(a)`   | Yaw left/right                                      |
| `&(a)` / `^(a)`   | Pitch down/up                                       |
| `/(a)` / `\(a)`   | Roll clockwise / counter-clockwise                  |
| `[` / `]`         | Push / pop turtle state                             |
| `!`               | Decrement branch radius by `radius_ratio` parameter |
| `~`               | Emit leaf surface at current position/orientation   |

Note: `\` is the standard L-system reverse-roll symbol. In Python strings use `\\`, in TOML use
`'\\'` or a literal string `'\'`. The tokeniser must handle this explicitly.

Tropism: apply a configurable gravity vector at each `F` step (bend direction towards **-Y** by
`tropism_weight`). This is what makes trees look like trees rather than wire sculptures.

Turtle state is a stack of `TurtleState(pos, frame, radius)` where `frame` is a 3×3 numpy
rotation matrix whose columns are the heading (H), left (L), and up (U) vectors. All rotations
are applied by multiplying rotation matrices — no per-step trig via `math.sin`/`math.cos`.
Extract H/L/U as `frame[:, 0]`, `frame[:, 1]`, `frame[:, 2]` when needed.

### 4. Preset files (`src/maidenhair/presets/*.toml`)

Each preset is a TOML file loaded with `tomllib` (stdlib). Example structure:

```toml
[meta]
name = "Adiantum capillus-veneris"
description = "Southern maidenhair fern"
reference = "Prusinkiewicz & Lindenmayer 1990, p.128"

[grammar]
axiom = "FFFFA"

[grammar.rules]
A = "F[+(48)B]F[-(48)B]FA"
B = "f[+(38)~]f[-(38)~]fB"

[params]
step_length = 0.8
radius_start = 0.04
radius_ratio = 0.75
angle_default = 25.0
tropism_weight = 0.12
iterations_default = 5
iterations_max = 7

[display]
leaf_color = [88, 155, 48]
branch_color = [30, 10, 2]
background_color = [7, 18, 10]
```

Validate presets with `pydantic` at load time. This makes the preset format self-documenting
and surfaces bad files early. The pydantic `PresetConfig` model should provide a method to
construct an `LSystem` instance directly, e.g. `preset.to_lsystem() -> LSystem`, so the
handoff between validation and the grammar engine is explicit.

Load presets at runtime via `importlib.resources.files("maidenhair.presets")` so they work both
in development (`uv run`) and after installation.

### 5. Software rasteriser (`render/viewport.py`)

Flet doesn't expose a native OpenGL context, so the live 3D viewport is a numpy→PIL→Flet
pipeline. It needs to be fast enough for interactive rotation.

- Project `segments` list using a perspective projection matrix (numpy vectorised over all segments at once)
- Sort by depth (painter's algorithm — sufficient for wireframe-style thin lines)
- Draw onto a PIL `ImageDraw` canvas using `line()` with width proportional to segment radius
- Return a PNG `bytes` object that Flet's `Image` control accepts via `src_base64`

**Performance note**: PIL's `ImageDraw.line()` is called per-segment, which is single-threaded.
To hit the <100ms target at 800×600, group segments by quantised width and batch each group into
a single `line()` polyline call where possible. If segment count exceeds ~10k, decimate the
geometry for the interactive view and use full geometry only for mesh export. The 50k threshold
in the original design may be too generous — profile and adjust.

The rasteriser is always wireframe-style (lines with varying width). It does not produce filled
surfaces. The mesh builder (`render/mesh.py`) handles solid geometry for export only.

Expose `Viewport` with:

```python
class Viewport:
    width: int
    height: int
    camera: Camera          # position, target, fov
    geometry: Geometry      # set on grammar recompute

    def rotate(self, dx: float, dy: float) -> None
    def zoom(self, delta: float) -> None
    def pan(self, dx: float, dy: float) -> None
    def render(self) -> bytes           # returns PNG bytes
```

Camera orbits around the bounding-box centre of the geometry. Target frame rate for rotation
drag: aim for <100ms per render at 800×600 on a modern laptop.

### 6. Mesh builder (`render/mesh.py`)

For export quality, convert each segment into a proper capped cylinder mesh using
`trimesh.creation.cylinder()`. Merge all cylinders with `trimesh.util.concatenate()`.
Optionally Boolean-union adjacent segments at branch points (expensive — make it opt-in).

Leaves become flat quad meshes oriented by their normal vector.

### 7. UI (`ui/`)

**Layout**: horizontal split. Left panel is the 3D canvas (takes remaining width). Right
sidebar is fixed ~320px.

**Sidebar sections** (collapsible):

- *Preset selector* — dropdown populated from `presets/*.toml`, plus a "Custom" entry that enables the raw rule editor
- *Iterations* — integer stepper 1–8, triggers full re-derive and re-render on change
- *Geometry parameters* — sliders for `step_length`, `radius_start`, `radius_ratio`, `tropism_weight`, `angle_default`. Sliders update geometry and re-render on release (not on every drag event — debounce to 300ms)
- *Display* — branch colour picker, leaf colour picker, background colour picker, wireframe toggle
- *Export* — buttons for OBJ, GLB, PLY, PNG export with a file picker dialog

**Canvas interaction**:

- Left-drag → orbit (calls `viewport.rotate(dx, dy)`, triggers `render()`)
- Scroll wheel → zoom (calls `viewport.zoom(delta)`)
- Right-drag (or two-finger drag) → pan camera target (calls `viewport.pan(dx, dy)`)
- All pointer events handled in Flet's `GestureDetector` wrapping the `Image` control

**Toolbar** (top bar):

- App title
- "Randomise stochastic" button (re-derives with different random seed, keeps params)
- "Reset camera" button
- Iteration progress indicator (shown during long derives)

**Async**: derivation and rendering run in `asyncio` tasks via `flet`'s `page.run_task()`.
The UI must not block. Show a spinner overlay on the canvas during recompute.

---

## CLI (`cli.py`)

```bash
# Render a preset to OBJ
uv run maidenhair render adiantum --iterations 5 --format obj --output adiantum.obj

# Render a preset to PNG (headless screenshot)
uv run maidenhair render adiantum --iterations 5 --format png --output adiantum.png

# List available presets
uv run maidenhair presets list

# Launch the GUI (equivalent to just run)
uv run maidenhair explore
```

Implemented with `typer`. The `render` command shares all core modules with the GUI — no
duplication. The `--format png` option uses the viewport rasteriser headlessly, which is the
natural first end-to-end test of the pipeline.

`src/maidenhair/__main__.py` calls `cli.app()` so `python -m maidenhair` works for debugging.

---

## `pyproject.toml`

```toml
[project]
name = "maidenhair"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = [
    "flet>=0.24",
    "numpy>=2.0",
    "trimesh>=4.4",
    "pillow>=10.0",
    "pydantic>=2.0",
    "typer>=0.12",
    "rich>=13.0",
]

[project.scripts]
maidenhair = "maidenhair.cli:app"

[build-system]
requires = ["uv_build>=0.7.5,<0.8"]
build-backend = "uv_build"

[tool.uv]
dev-dependencies = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "ruff>=0.4",
    "ty",
    "bump-my-version",
    "pre-commit",
]

[tool.bumpversion]
current_version = "0.1.0"
commit = true
tag = true
tag_name = "release/{new_version}"

[[tool.bumpversion.files]]
filename = "pyproject.toml"
search = 'version = "{current_version}"'
replace = 'version = "{new_version}"'

[[tool.bumpversion.files]]
filename = "src/maidenhair/__init__.py"
search = '__version__ = "{current_version}"'
replace = '__version__ = "{new_version}"'
```

Note: `toml` is dropped — Python 3.13 has `tomllib` in the stdlib. `requires-python` is
`>=3.13` to match `.python-version` and guarantee `tomllib` availability.

---

## `.pre-commit-config.yaml`

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: check-yaml
      - id: end-of-file-fixer
      - id: trailing-whitespace
      - id: check-merge-conflict
      - id: detect-aws-credentials
        args: [--allow-missing-credentials]
      - id: check-json

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.9.0
    hooks:
      - id: ruff
      - id: ruff-format

  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.5.0
    hooks:
      - id: detect-secrets
        args: [--baseline, .secrets.baseline]

  - repo: local
    hooks:
      - id: ty
        name: ty type check
        entry: ty check src/
        language: system
        pass_filenames: false
        types: [python]
```

---

## `.envrc`

```bash
watch_file .env
dotenv_if_exists
source .venv/bin/activate
pre-commit install --allow-missing-config 2>/dev/null
```

---

## `justfile`

```makefile
dev:
    uv run flet run src/maidenhair/ui/app.py

run:
    uv run maidenhair explore

test:
    uv run pytest tests/ -v

lint:
    uv run ruff check src/ tests/
    uv run ty check src/

format:
    uv run ruff format src/ tests/

export preset="adiantum" iter="5" fmt="glb":
    uv run maidenhair render {{preset}} --iterations {{iter}} --format {{fmt}}

build-web:
    uv run flet build web src/maidenhair/ui/app.py

build-linux:
    uv run flet build linux src/maidenhair/ui/app.py

build-windows:
    uv run flet build windows src/maidenhair/ui/app.py

version bump="patch":
    bump-my-version bump {{bump}}
```

---

## Testing

Write unit tests for:

- `grammar.py` — derivation correctness against known L-system outputs (algae, Koch, Sierpinski); stochastic seed reproducibility; max_string_length guard
- `parametric.py` — tokeniser round-trips; backslash (`\`) symbol handling
- `turtle3d.py` — push/pop stack integrity, bounding box non-zero for any `F` step, coordinate convention (growth in +Y)
- `presets.py` — all bundled presets validate against pydantic schema; `to_lsystem()` produces a working `LSystem`
- `render/viewport.py` — `render()` returns valid PNG bytes, non-zero image; `pan()` shifts camera target

No rendering tests need visual comparison — just structural integrity.

---

## Implementation order for Claude Code

1. `core/parametric.py` + tests — tokeniser for `Symbol(name, params)`, needed by all presets
2. `core/grammar.py` + tests — string rewriting (deterministic + stochastic), seed control, max_string_length guard
3. `core/turtle3d.py` + tests — geometry output consuming `Symbol` list, coordinate convention (+Y up, -Y gravity)
4. `src/maidenhair/presets/*.toml` + `core/presets.py` — pydantic validation, `to_lsystem()`, `importlib.resources` loading
5. `render/viewport.py` — numpy rasteriser, test with a static `Geometry`
6. `cli.py` + `__main__.py` — headless render to PNG (`--format png`) to verify the pipeline end-to-end
7. `ui/app.py` + `ui/canvas.py` — bare Flet window showing the rasterised image
8. `ui/sidebar.py` — sliders wired to parameter recompute
9. `render/mesh.py` + `render/export.py` — trimesh output
10. `ui/toolbar.py` + export dialogs — complete the UI
11. Polish: debounce, async spinner, camera reset, colour pickers

---

## Constraints

- Keep `core/` completely free of any UI or rendering imports. It must be importable headlessly for the CLI and for tests.
- The rasteriser in `render/viewport.py` must not import `flet`. It takes a `Geometry` and returns `bytes`. The Flet integration lives entirely in `ui/canvas.py`.
- All angles in the grammar and parameter files are in **degrees**. Convert to radians only inside `turtle3d.py` at the point of use.
- `trimesh` is used only in `render/` — never in `core/`. This keeps the grammar and turtle layers dependency-free.
- The TOML preset format is the public API for adding new plants. Document it in `README.md` so a user can add a new preset without touching Python.
- Coordinate system is Y-up, right-handed. Gravity is -Y. Do not mix conventions.

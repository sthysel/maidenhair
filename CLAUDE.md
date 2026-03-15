# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Maidenhair is a cross-platform desktop/web application for interactively exploring parametric L-system plant models with real-time 3D visualisation and export. Built with Python 3.13, flet (Flutter-backed UI), numpy, trimesh, and typer.

## Coordinate System

Y-up, right-handed. Turtle starts at origin facing +Y. Gravity is -Y. Camera default looks down -Z.

## Commands

```bash
uv sync                          # install dependencies
uv run pytest tests/ -v          # run tests
uv run pytest tests/test_foo.py::test_bar -v  # run a single test
uv run pre-commit run --all-files  # lint and format
uv run ty check src/             # type check
just dev                         # launch flet dev mode (hot reload)
just run                         # launch GUI via CLI entry point
just test                        # run tests
just lint                        # ruff check + ty check
just format                      # ruff format
just version patch               # bump version
just export preset="adiantum" iter="5" fmt="glb"  # headless export
```

CLI entry point: `uv run maidenhair <command>` (render, presets list, explore). Also `python -m maidenhair` via `__main__.py`.

## Build System

- `uv` for package management with `uv_build` backend — no pip/poetry/setuptools
- `justfile` as task runner
- All config in `pyproject.toml`
- `bump-my-version` for versioning (NOT `bumpversion`), tag format `release/{version}`
- Python >=3.13 — uses `tomllib` from stdlib (no third-party `toml` package)
- `pre-commit` with ruff, detect-secrets, and local ty hook
- `.envrc` for direnv: activates venv, installs pre-commit hooks
- `scipy` is required at runtime (trimesh uses it for face-to-vertex color conversion during mesh export)
- ty excludes `ui/` from type checking (flet stubs are incomplete); core/ and render/ are fully checked

## Architecture

Three strict layers with enforced import boundaries:

### `core/` — Pure logic, no UI or rendering imports
- **`parametric.py`** — Tokeniser for parametric symbols like `F(2.5)`, `+(30)`, `\(45)`. Produces `Symbol(name, params)` list. Non-parametric fast path. Needed from the start — all bundled presets use parametric syntax.
- **`grammar.py`** — `LSystem` dataclass: string rewriting (deterministic + stochastic). `seed` parameter for reproducible stochastic derivation. `max_string_length` guard (default 50M chars) prevents runaway memory at high iterations.
- **`turtle3d.py`** — 3D turtle interpreter. Consumes `Symbol` list, produces `Geometry` (segments + leaves). `TurtleState(pos, frame, radius)` where `frame` is a 3x3 rotation matrix (columns = H, L, U vectors). Tropism bends toward -Y.
- **`presets.py`** — Loads/validates TOML presets with pydantic via `importlib.resources`. `PresetConfig.to_lsystem() -> LSystem` bridges validation to the grammar engine.

### `render/` — Geometry to pixels/meshes, no flet imports
- **`viewport.py`** — numpy software rasteriser → PIL → PNG bytes. Wireframe-style only (lines with varying width, not filled surfaces). Groups segments by quantised width for batched PIL drawing. Decimates geometry >~10k segments for interactive use.
- **`mesh.py`** — trimesh cylinder/cone mesh builder for export quality (solid geometry).
- **`export.py`** — OBJ/GLB/PLY writer via trimesh.

### `ui/` — Flet application
- **`app.py`** — flet.app() entry point
- **`canvas.py`** — Wraps `Viewport` output into Flet `Image` control via `src_base64`. All flet-render integration lives here.
- **`sidebar.py`** — Parameter sliders, preset selector, colour pickers, export buttons. Debounce 300ms.
- **`toolbar.py`** — Randomise stochastic (new seed), reset camera, iteration progress.

### Presets
TOML files in `src/maidenhair/presets/` (package data, loaded via `importlib.resources`). Public API for adding new plants.

### Key constraints
- `core/` must never import from `render/` or `ui/`
- `render/viewport.py` must never import `flet`
- `trimesh` only in `render/`, never in `core/`
- All angles in grammar/preset files are **degrees** — convert to radians only inside `turtle3d.py`
- `\` (backslash) is the reverse-roll symbol — handle escaping in Python strings and TOML

### Data flow
```
TOML preset → PresetConfig.to_lsystem() → LSystem.derive(n, seed=) → derivation string
  → parametric.tokenise() → [Symbol] → Turtle3D.interpret() → Geometry
    → Viewport.render() → PNG bytes → Flet Image (interactive) or file (CLI --format png)
    → MeshBuilder → trimesh → OBJ/GLB/PLY (export)
```

### Async model
Derivation and rendering run as `asyncio` tasks via `page.run_task()`. Canvas shows a spinner overlay during recompute. Camera drag targets <100ms render at 800x600.

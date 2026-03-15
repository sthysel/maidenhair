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

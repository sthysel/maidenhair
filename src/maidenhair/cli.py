"""CLI for maidenhair — headless render and batch export."""

from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from maidenhair.core.parametric import tokenise
from maidenhair.core.presets import list_bundled_presets, load_preset
from maidenhair.core.turtle3d import interpret
from maidenhair.render.export import export_mesh
from maidenhair.render.viewport import Viewport

app = typer.Typer(help="Maidenhair — L-System Botanical Explorer")
console = Console()


class OutputFormat(StrEnum):
    obj = "obj"
    glb = "glb"
    ply = "ply"
    png = "png"


@app.command()
def render(
    preset_name: Annotated[str, typer.Argument(help="Name of a bundled preset")],
    iterations: Annotated[int, typer.Option("--iterations", "-n", help="Number of derivation iterations")] = 4,
    output: Annotated[Path | None, typer.Option("--output", "-o", help="Output file path")] = None,
    fmt: Annotated[OutputFormat, typer.Option("--format", "-f", help="Output format")] = OutputFormat.glb,
    seed: Annotated[int | None, typer.Option("--seed", "-s", help="Random seed for stochastic rules")] = None,
    width: Annotated[int, typer.Option("--width", help="PNG render width")] = 800,
    height: Annotated[int, typer.Option("--height", help="PNG render height")] = 600,
) -> None:
    """Render a preset to a 3D file or PNG image."""
    presets = list_bundled_presets()
    if preset_name not in presets:
        console.print(f"[red]Unknown preset: {preset_name}[/red]")
        console.print(f"Available: {', '.join(sorted(presets.keys()))}")
        raise typer.Exit(1)

    preset = load_preset(presets[preset_name])
    lsystem = preset.to_lsystem()

    if output is None:
        output = Path(f"{preset_name}.{fmt.value}")

    console.print(f"Deriving [bold]{preset.meta.name}[/bold] for {iterations} iterations...")
    derivation = lsystem.derive(iterations, seed=seed)
    console.print(f"  String length: {len(derivation):,}")

    console.print("Interpreting turtle commands...")
    symbols = tokenise(derivation)
    geometry = interpret(
        symbols,
        step_length=preset.params.step_length,
        angle_default=preset.params.angle_default,
        radius_start=preset.params.radius_start,
        radius_ratio=preset.params.radius_ratio,
        tropism_weight=preset.params.tropism_weight,
    )
    console.print(f"  Segments: {len(geometry.segments):,}, Leaves: {len(geometry.leaves):,}")

    if fmt == OutputFormat.png:
        console.print(f"Rendering to PNG ({width}x{height})...")
        vp = Viewport(
            width=width,
            height=height,
            branch_color=tuple(preset.display.branch_color),  # type: ignore[arg-type]
            leaf_color=tuple(preset.display.leaf_color),  # type: ignore[arg-type]
            background_color=tuple(preset.display.background_color),  # type: ignore[arg-type]
        )
        vp.set_geometry(geometry)
        png_bytes = vp.render_png()
        output.write_bytes(png_bytes)
    else:
        console.print(f"Exporting to {fmt.value.upper()}...")
        export_mesh(
            geometry,
            output,
            file_format=fmt.value,
            branch_color=tuple(preset.display.branch_color),  # type: ignore[arg-type]
            leaf_color=tuple(preset.display.leaf_color),  # type: ignore[arg-type]
        )

    console.print(f"[green]Saved to {output}[/green]")


@app.command(name="presets")
def presets_cmd(
    action: Annotated[str, typer.Argument(help="Action: 'list'")] = "list",
) -> None:
    """List available presets."""
    if action != "list":
        console.print(f"[red]Unknown action: {action}[/red]")
        raise typer.Exit(1)

    presets = list_bundled_presets()
    table = Table(title="Available Presets")
    table.add_column("Name", style="bold")
    table.add_column("Description")

    for name, path in sorted(presets.items()):
        preset = load_preset(path)
        table.add_row(name, preset.meta.description)

    console.print(table)


@app.command()
def explore() -> None:
    """Launch the interactive GUI."""
    from maidenhair.ui.app import main

    main()


if __name__ == "__main__":
    app()

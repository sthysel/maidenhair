"""Export L-system geometry to standard 3D file formats."""

from __future__ import annotations

from pathlib import Path

from maidenhair.core.turtle3d import Geometry
from maidenhair.render.mesh import build_mesh


def export_mesh(
    geometry: Geometry,
    output_path: Path,
    *,
    file_format: str | None = None,
    branch_color: tuple[int, int, int] = (30, 10, 2),
    leaf_color: tuple[int, int, int] = (88, 155, 48),
) -> None:
    """Export geometry to a 3D file (OBJ, GLB, PLY).

    If file_format is None, it's inferred from the file extension.
    """
    mesh = build_mesh(geometry, branch_color=branch_color, leaf_color=leaf_color)

    if file_format is None:
        file_format = output_path.suffix.lstrip(".")

    format_map = {
        "obj": "obj",
        "glb": "glb",
        "ply": "ply",
        "stl": "stl",
    }

    fmt = format_map.get(file_format.lower(), file_format.lower())
    mesh.export(str(output_path), file_type=fmt)

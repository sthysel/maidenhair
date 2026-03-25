"""Mesh builder for export-quality L-system geometry.

Converts segments into trimesh cylinder meshes and leaves into quad meshes.
"""

import numpy as np
import trimesh

from maidenhair.core.turtle3d import Geometry


def build_mesh(
    geometry: Geometry,
    *,
    branch_color: tuple[int, int, int] = (30, 10, 2),
    leaf_color: tuple[int, int, int] = (88, 155, 48),
    segments_per_cylinder: int = 6,
) -> trimesh.Trimesh:
    """Convert L-system geometry into a trimesh mesh.

    Each segment becomes a cylinder. Leaves become flat quads.
    """
    meshes: list[trimesh.Trimesh] = []

    for start, end, radius in geometry.segments:
        direction = end - start
        height = float(np.linalg.norm(direction))
        if height < 1e-10:
            continue

        cyl = trimesh.creation.cylinder(
            radius=radius,
            height=height,
            sections=segments_per_cylinder,
        )

        # Align cylinder (default along Z) to the segment direction
        direction_norm = direction / height
        z_axis = np.array([0.0, 0.0, 1.0])

        # Rotation from Z to direction
        cross = np.cross(z_axis, direction_norm)
        cross_len = np.linalg.norm(cross)
        dot = np.dot(z_axis, direction_norm)

        if cross_len > 1e-10:
            cross_norm = cross / cross_len
            angle = np.arctan2(cross_len, dot)
            rot_matrix = trimesh.transformations.rotation_matrix(angle, cross_norm)
        elif dot < 0:
            rot_matrix = trimesh.transformations.rotation_matrix(np.pi, [1.0, 0.0, 0.0])
        else:
            rot_matrix = np.eye(4)

        # Translate to midpoint
        midpoint = (start + end) / 2.0
        translation = trimesh.transformations.translation_matrix(midpoint)

        cyl.apply_transform(rot_matrix)
        cyl.apply_transform(translation)

        # Apply color
        cyl.visual.face_colors = [(*branch_color, 255)] * len(cyl.faces)
        meshes.append(cyl)

    # Build leaf quads
    leaf_size = 0.15
    for pos, normal, _left in geometry.leaves:
        normal_norm = normal / (np.linalg.norm(normal) + 1e-10)

        # Create a small quad perpendicular to the normal
        # Find two perpendicular vectors
        if abs(normal_norm[1]) < 0.9:
            tangent = np.cross(normal_norm, [0, 1, 0])
        else:
            tangent = np.cross(normal_norm, [1, 0, 0])
        tangent = tangent / (np.linalg.norm(tangent) + 1e-10)
        bitangent = np.cross(normal_norm, tangent)

        half = leaf_size / 2.0
        vertices = np.array(
            [
                pos - tangent * half - bitangent * half,
                pos + tangent * half - bitangent * half,
                pos + tangent * half + bitangent * half,
                pos - tangent * half + bitangent * half,
            ]
        )
        faces = np.array([[0, 1, 2], [0, 2, 3]])
        leaf_mesh = trimesh.Trimesh(vertices=vertices, faces=faces)
        leaf_mesh.visual.face_colors = [(*leaf_color, 255)] * len(leaf_mesh.faces)  # type: ignore[assignment]
        meshes.append(leaf_mesh)

    if not meshes:
        return trimesh.Trimesh()

    return trimesh.util.concatenate(meshes)

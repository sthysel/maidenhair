"""Software rasteriser for L-system geometry.

numpy -> PIL -> image bytes pipeline. No flet imports.
Wireframe-style with depth shading and perspective-correct widths.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field

import numpy as np
from PIL import Image, ImageDraw

from maidenhair.core.turtle3d import Geometry

# Maximum segment count for interactive rendering before decimation
MAX_INTERACTIVE_SEGMENTS = 10_000


@dataclass
class Camera:
    """Orbiting camera around a target point."""

    position: np.ndarray = field(default_factory=lambda: np.array([0.0, 2.0, 8.0]))
    target: np.ndarray = field(default_factory=lambda: np.array([0.0, 2.0, 0.0]))
    fov: float = 45.0  # degrees
    azimuth: float = 0.0  # radians
    elevation: float = 0.3  # radians
    distance: float = 8.0

    def update_position(self) -> None:
        """Recompute position from spherical coordinates."""
        ce = np.cos(self.elevation)
        se = np.sin(self.elevation)
        sa = np.sin(self.azimuth)
        ca = np.cos(self.azimuth)
        self.position = self.target + np.array(
            [
                self.distance * ce * sa,
                self.distance * se,
                self.distance * ce * ca,
            ]
        )


@dataclass
class Viewport:
    """Software 3D viewport that renders Geometry to image bytes."""

    width: int = 800
    height: int = 600
    camera: Camera = field(default_factory=Camera)
    geometry: Geometry | None = None
    branch_color: tuple[int, int, int] = (140, 90, 44)
    leaf_color: tuple[int, int, int] = (88, 180, 48)
    background_color: tuple[int, int, int] = (12, 22, 16)

    # Cached projected geometry (invalidated on geometry or camera change)
    _projected_segments: np.ndarray | None = field(default=None, repr=False)
    _projected_leaves: np.ndarray | None = field(default=None, repr=False)
    _camera_hash: int = field(default=0, repr=False)

    def set_geometry(self, geometry: Geometry) -> None:
        """Set geometry and auto-fit camera to bounding box."""
        self.geometry = geometry
        self._projected_segments = None
        self._projected_leaves = None
        if geometry.segments:
            centre = geometry.centre()
            mn, mx = geometry.bounding_box()
            extent = float(np.linalg.norm(mx - mn))
            self.camera.target = centre.copy()
            self.camera.distance = max(extent * 1.5, 1.0)
            self.camera.update_position()

    def rotate(self, dx: float, dy: float) -> None:
        """Orbit camera by pixel deltas."""
        self.camera.azimuth += dx * 0.005
        self.camera.elevation = float(
            np.clip(
                self.camera.elevation + dy * 0.005,
                -np.pi / 2 + 0.01,
                np.pi / 2 - 0.01,
            )
        )
        self.camera.update_position()
        self._projected_segments = None
        self._projected_leaves = None

    def zoom(self, delta: float) -> None:
        """Zoom camera by scroll delta."""
        factor = 1.1 if delta > 0 else 0.9
        self.camera.distance = max(0.1, self.camera.distance * factor)
        self.camera.update_position()
        self._projected_segments = None
        self._projected_leaves = None

    def pan(self, dx: float, dy: float) -> None:
        """Pan camera target by pixel deltas."""
        forward = self.camera.target - self.camera.position
        fwd_len = np.linalg.norm(forward)
        if fwd_len < 1e-10:
            return
        forward = forward / fwd_len
        world_up = np.array([0.0, 1.0, 0.0])
        right = np.cross(forward, world_up)
        right_len = np.linalg.norm(right)
        if right_len < 1e-10:
            return
        right = right / right_len
        up = np.cross(right, forward)

        sensitivity = self.camera.distance * 0.002
        self.camera.target = self.camera.target + right * (-dx * sensitivity) + up * (dy * sensitivity)
        self.camera.update_position()
        self._projected_segments = None
        self._projected_leaves = None

    def render_image(self) -> Image.Image:
        """Render geometry to a PIL Image."""
        img = Image.new("RGB", (self.width, self.height), self.background_color)

        if self.geometry is None or (not self.geometry.segments and not self.geometry.leaves):
            return img

        draw = ImageDraw.Draw(img)

        # Build view-projection matrix
        vp = _build_vp_matrix(self.camera, self.width / self.height)
        half_w = self.width / 2.0
        half_h = self.height / 2.0

        # Project and draw segments
        if self.geometry.segments:
            self._draw_segments(draw, vp, half_w, half_h)

        # Project and draw leaves
        if self.geometry.leaves:
            self._draw_leaves(draw, vp, half_w, half_h)

        return img

    def render(self) -> bytes:
        """Render geometry to BMP bytes (fast, no compression — for interactive use)."""
        return _image_to_bmp(self.render_image())

    def render_png(self) -> bytes:
        """Render geometry to PNG bytes (for file export)."""
        return _image_to_png(self.render_image())

    def _draw_segments(self, draw: ImageDraw.ImageDraw, vp: np.ndarray, half_w: float, half_h: float) -> None:
        assert self.geometry is not None
        segments = self.geometry.segments

        # Decimate if needed
        if len(segments) > MAX_INTERACTIVE_SEGMENTS:
            step = len(segments) // MAX_INTERACTIVE_SEGMENTS
            segments = segments[::step]

        n = len(segments)
        if n == 0:
            return

        # Vectorised projection: build (n, 3) arrays for starts, ends, radii
        starts = np.empty((n, 3), dtype=np.float64)
        ends = np.empty((n, 3), dtype=np.float64)
        radii = np.empty(n, dtype=np.float64)
        for i, (s, e, r) in enumerate(segments):
            starts[i] = s
            ends[i] = e
            radii[i] = r

        # Project all points at once: (n, 4) homogeneous
        s_screen, s_depth, s_mask = _project_points_batch(vp, starts, half_w, half_h)
        e_screen, e_depth, e_mask = _project_points_batch(vp, ends, half_w, half_h)

        # Only draw segments where both endpoints are visible
        mask = s_mask & e_mask
        if not np.any(mask):
            return

        sx = s_screen[mask, 0]
        sy = s_screen[mask, 1]
        ex = e_screen[mask, 0]
        ey = e_screen[mask, 1]
        avg_depth = (s_depth[mask] + e_depth[mask]) * 0.5
        seg_radii = radii[mask]

        # Depth range for shading
        min_depth = avg_depth.min()
        max_depth = avg_depth.max()
        depth_range = max_depth - min_depth
        if depth_range < 1e-6:
            depth_range = 1.0

        # Normalised depth: 0 = near, 1 = far
        norm_depth = (avg_depth - min_depth) / depth_range

        # Compute screen-space widths from radius and depth
        # Perspective: width = radius * focal_length / depth
        focal = half_h / np.tan(self.camera.fov * np.pi / 360.0)
        widths = np.clip(seg_radii * focal / np.maximum(avg_depth, 0.1), 1, 30).astype(int)

        # Sort by depth (far first — painter's algorithm)
        order = np.argsort(-avg_depth)

        # Base color
        br, bg, bb = self.branch_color

        # Draw segments with depth shading
        for idx in order:
            t = float(norm_depth[idx])
            # Shade: near segments are full brightness, far ones fade to 30%
            shade = 1.0 - t * 0.7
            cr = int(br * shade)
            cg = int(bg * shade)
            cb = int(bb * shade)
            w = int(widths[idx])
            draw.line(
                [(float(sx[idx]), float(sy[idx])), (float(ex[idx]), float(ey[idx]))],
                fill=(cr, cg, cb),
                width=w,
            )

    def _draw_leaves(self, draw: ImageDraw.ImageDraw, vp: np.ndarray, half_w: float, half_h: float) -> None:
        assert self.geometry is not None
        n = len(self.geometry.leaves)
        if n == 0:
            return

        positions = np.empty((n, 3), dtype=np.float64)
        for i, (pos, _heading, _left) in enumerate(self.geometry.leaves):
            positions[i] = pos

        screen, depth, mask = _project_points_batch(vp, positions, half_w, half_h)
        if not np.any(mask):
            return

        px = screen[mask, 0]
        py = screen[mask, 1]
        leaf_depth = depth[mask]

        # Depth shading for leaves
        min_d = leaf_depth.min()
        max_d = leaf_depth.max()
        d_range = max_d - min_d
        if d_range < 1e-6:
            d_range = 1.0
        norm_d = (leaf_depth - min_d) / d_range

        # Perspective leaf size
        focal = half_h / np.tan(self.camera.fov * np.pi / 360.0)
        ls = self.geometry.leaf_size
        leaf_radii = np.clip(ls * focal / np.maximum(leaf_depth, 0.1), 2, 12)

        lr, lg, lb = self.leaf_color

        # Sort far-to-near
        order = np.argsort(-leaf_depth)
        for idx in order:
            t = float(norm_d[idx])
            shade = 1.0 - t * 0.6
            cr = int(lr * shade)
            cg = int(lg * shade)
            cb = int(lb * shade)
            r = float(leaf_radii[idx])
            x, y = float(px[idx]), float(py[idx])
            draw.ellipse([x - r, y - r, x + r, y + r], fill=(cr, cg, cb))


def _build_vp_matrix(camera: Camera, aspect: float) -> np.ndarray:
    """Build combined view-projection matrix."""
    view = _look_at(camera.position, camera.target)
    fov_rad = camera.fov * np.pi / 180.0
    proj = _perspective(fov_rad, aspect, 0.1, 1000.0)
    return proj @ view


def _project_points_batch(
    vp: np.ndarray, points: np.ndarray, half_w: float, half_h: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Project an (n, 3) array of points to screen coords.

    Returns:
        screen: (n, 2) screen x, y
        depth: (n,) clip-space depth (positive = in front)
        mask: (n,) bool — True if point is in front of camera
    """
    n = points.shape[0]
    # Build (n, 4) homogeneous coordinates
    ones = np.ones((n, 1), dtype=np.float64)
    homo = np.hstack([points, ones])  # (n, 4)

    # Transform: (4, 4) @ (4, n) -> (4, n) -> transpose to (n, 4)
    clip = (vp @ homo.T).T  # (n, 4)

    w = clip[:, 3]
    mask = w > 0.01

    # Avoid division by zero for masked-out points
    w_safe = np.where(mask, w, 1.0)
    ndc_x = clip[:, 0] / w_safe
    ndc_y = clip[:, 1] / w_safe
    screen = np.empty((n, 2), dtype=np.float64)
    screen[:, 0] = ndc_x * half_w + half_w
    screen[:, 1] = -ndc_y * half_h + half_h

    return screen, w, mask


def _image_to_bmp(img: Image.Image) -> bytes:
    """Encode image as BMP (no compression — much faster than PNG)."""
    buf = io.BytesIO()
    img.save(buf, format="BMP")
    return buf.getvalue()


def _image_to_png(img: Image.Image) -> bytes:
    """Encode image as PNG (for file export)."""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _look_at(eye: np.ndarray, target: np.ndarray) -> np.ndarray:
    """Create a 4x4 view matrix (look-at)."""
    up = np.array([0.0, 1.0, 0.0])
    forward = target - eye
    fwd_len = np.linalg.norm(forward)
    if fwd_len < 1e-10:
        return np.eye(4)
    forward = forward / fwd_len
    right = np.cross(forward, up)
    right_len = np.linalg.norm(right)
    if right_len < 1e-10:
        up = np.array([0.0, 0.0, 1.0])
        right = np.cross(forward, up)
        right_len = np.linalg.norm(right)
    right = right / right_len
    up = np.cross(right, forward)

    mat = np.eye(4)
    mat[0, :3] = right
    mat[1, :3] = up
    mat[2, :3] = -forward
    mat[0, 3] = -np.dot(right, eye)
    mat[1, 3] = -np.dot(up, eye)
    mat[2, 3] = np.dot(forward, eye)
    return mat


def _perspective(fov: float, aspect: float, near: float, far: float) -> np.ndarray:
    """Create a 4x4 perspective projection matrix."""
    f = 1.0 / np.tan(fov / 2.0)
    mat = np.zeros((4, 4))
    mat[0, 0] = f / aspect
    mat[1, 1] = f
    mat[2, 2] = (far + near) / (near - far)
    mat[2, 3] = (2.0 * far * near) / (near - far)
    mat[3, 2] = -1.0
    return mat

"""OpenGL hardware-accelerated viewport using moderngl.

Renders L-system geometry with:
- GPU-side billboard expansion (geometry uploaded once, quads computed in vertex shader)
- Depth testing (proper occlusion)
- MSAA anti-aliasing
- Depth-based fog shading
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field

import moderngl
import numpy as np
from PIL import Image

from maidenhair.core.turtle3d import Geometry

# Vertex shader: billboard expansion on GPU.
# Each vertex carries the full segment (start, end, radius) plus a corner ID.
# The shader computes the camera-facing perpendicular and offsets the position.
_VERTEX_SHADER = """
#version 330

uniform mat4 u_mvp;
uniform vec3 u_camera_pos;

in vec3 in_seg_start;
in vec3 in_seg_end;
in float in_radius;
in vec3 in_color;
in float in_side;   // -1 or +1 (left/right of line)
in float in_end_t;  // 0 = start, 1 = end

out vec3 v_color;
out float v_depth;

void main() {
    vec3 pos = mix(in_seg_start, in_seg_end, in_end_t);
    vec3 seg_dir = in_seg_end - in_seg_start;
    float seg_len = length(seg_dir);

    if (seg_len > 0.0001) {
        seg_dir /= seg_len;
    } else {
        seg_dir = vec3(0.0, 1.0, 0.0);
    }

    // View direction from camera to this vertex
    vec3 to_cam = u_camera_pos - pos;
    // Perpendicular in camera-facing plane
    vec3 perp = cross(seg_dir, to_cam);
    float perp_len = length(perp);
    if (perp_len < 0.0001) {
        perp = cross(seg_dir, vec3(0.0, 1.0, 0.0));
        perp_len = length(perp);
        if (perp_len < 0.0001) {
            perp = cross(seg_dir, vec3(1.0, 0.0, 0.0));
            perp_len = length(perp);
        }
    }
    perp = (perp / perp_len) * in_radius * in_side;
    pos += perp;

    gl_Position = u_mvp * vec4(pos, 1.0);
    v_color = in_color;
    v_depth = gl_Position.w;
}
"""

_FRAGMENT_SHADER = """
#version 330

uniform float u_fog_near;
uniform float u_fog_far;
uniform vec3 u_bg_color;

in vec3 v_color;
in float v_depth;

out vec4 f_color;

void main() {
    float fog = clamp((v_depth - u_fog_near) / (u_fog_far - u_fog_near), 0.0, 0.8);
    vec3 color = mix(v_color, u_bg_color * 1.5, fog);
    f_color = vec4(color, 1.0);
}
"""

# Billboard leaf shader: simple point-based with camera-facing quad
_LEAF_VERTEX_SHADER = """
#version 330

uniform mat4 u_mvp;
uniform vec3 u_cam_right;
uniform vec3 u_cam_up;

in vec3 in_position;
in vec3 in_color;
in float in_side_x;  // -1 or +1
in float in_side_y;  // -1 or +1
in float in_size;

out vec3 v_color;
out float v_depth;

void main() {
    vec3 pos = in_position + u_cam_right * in_side_x * in_size + u_cam_up * in_side_y * in_size;
    gl_Position = u_mvp * vec4(pos, 1.0);
    v_color = in_color;
    v_depth = gl_Position.w;
}
"""

SAMPLES = 4


@dataclass
class Camera:
    """Orbiting camera around a target point."""

    position: np.ndarray = field(default_factory=lambda: np.array([0.0, 2.0, 8.0]))
    target: np.ndarray = field(default_factory=lambda: np.array([0.0, 2.0, 0.0]))
    fov: float = 45.0
    azimuth: float = 0.0
    elevation: float = 0.3
    distance: float = 8.0

    def update_position(self) -> None:
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
class GLViewport:
    """Hardware-accelerated 3D viewport using moderngl."""

    width: int = 800
    height: int = 600
    camera: Camera = field(default_factory=Camera)
    geometry: Geometry | None = None
    branch_color: tuple[int, int, int] = (140, 90, 44)
    leaf_color: tuple[int, int, int] = (88, 180, 48)
    background_color: tuple[int, int, int] = (12, 22, 16)

    _ctx: moderngl.Context | None = field(default=None, repr=False, init=False)
    _seg_prog: moderngl.Program | None = field(default=None, repr=False, init=False)
    _leaf_prog: moderngl.Program | None = field(default=None, repr=False, init=False)
    _fbo: moderngl.Framebuffer | None = field(default=None, repr=False, init=False)
    _fbo_resolve: moderngl.Framebuffer | None = field(default=None, repr=False, init=False)
    _vao_segments: moderngl.VertexArray | None = field(default=None, repr=False, init=False)
    _vao_leaves: moderngl.VertexArray | None = field(default=None, repr=False, init=False)
    _n_seg_verts: int = field(default=0, repr=False, init=False)
    _n_leaf_verts: int = field(default=0, repr=False, init=False)
    _prev_fbo_size: tuple[int, int] = field(default=(0, 0), repr=False, init=False)

    def _ensure_context(self) -> None:
        if self._ctx is None:
            self._ctx = moderngl.create_standalone_context()
            self._seg_prog = self._ctx.program(
                vertex_shader=_VERTEX_SHADER,
                fragment_shader=_FRAGMENT_SHADER,
            )
            self._leaf_prog = self._ctx.program(
                vertex_shader=_LEAF_VERTEX_SHADER,
                fragment_shader=_FRAGMENT_SHADER,
            )

    def _ensure_fbo(self) -> None:
        self._ensure_context()
        assert self._ctx is not None
        size = (max(self.width, 1), max(self.height, 1))
        if self._prev_fbo_size == size:
            return
        if self._fbo is not None:
            self._fbo.release()
        if self._fbo_resolve is not None:
            self._fbo_resolve.release()
        self._fbo = self._ctx.framebuffer(
            color_attachments=[self._ctx.renderbuffer(size, samples=SAMPLES)],
            depth_attachment=self._ctx.depth_renderbuffer(size, samples=SAMPLES),
        )
        self._fbo_resolve = self._ctx.framebuffer(
            color_attachments=[self._ctx.renderbuffer(size)],
        )
        self._prev_fbo_size = size

    def set_geometry(self, geometry: Geometry) -> None:
        """Set geometry, upload to GPU, and auto-fit camera."""
        self.geometry = geometry
        self._upload_geometry()
        if geometry.segments:
            centre = geometry.centre()
            mn, mx = geometry.bounding_box()
            extent = float(np.linalg.norm(mx - mn))
            self.camera.target = centre.copy()
            self.camera.distance = max(extent * 1.5, 1.0)
            self.camera.update_position()

    def rotate(self, dx: float, dy: float) -> None:
        self.camera.azimuth += dx * 0.005
        self.camera.elevation = float(
            np.clip(
                self.camera.elevation + dy * 0.005,
                -np.pi / 2 + 0.01,
                np.pi / 2 - 0.01,
            )
        )
        self.camera.update_position()

    def zoom(self, delta: float) -> None:
        factor = 1.1 if delta > 0 else 0.9
        self.camera.distance = max(0.1, self.camera.distance * factor)
        self.camera.update_position()

    def pan(self, dx: float, dy: float) -> None:
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
        right /= right_len
        up = np.cross(right, forward)
        sensitivity = self.camera.distance * 0.002
        self.camera.target = self.camera.target + right * (-dx * sensitivity) + up * (dy * sensitivity)
        self.camera.update_position()

    def _upload_geometry(self) -> None:
        """Build and upload vertex data to GPU. Called once per geometry change."""
        self._ensure_context()
        assert self._ctx is not None
        assert self._seg_prog is not None
        assert self._leaf_prog is not None

        if self._vao_segments is not None:
            self._vao_segments.release()
            self._vao_segments = None
        if self._vao_leaves is not None:
            self._vao_leaves.release()
            self._vao_leaves = None
        self._n_seg_verts = 0
        self._n_leaf_verts = 0

        if self.geometry is None:
            return

        br = self.branch_color[0] / 255.0
        bg = self.branch_color[1] / 255.0
        bb = self.branch_color[2] / 255.0

        # Upload segment data — 6 vertices per segment
        # Layout: seg_start(3f) seg_end(3f) radius(1f) color(3f) side(1f) end_t(1f) = 12 floats
        if self.geometry.segments:
            segs = self.geometry.segments
            n = len(segs)

            starts = np.empty((n, 3), dtype=np.float32)
            ends = np.empty((n, 3), dtype=np.float32)
            radii = np.empty(n, dtype=np.float32)
            for i, (s, e, r) in enumerate(segs):
                starts[i] = s
                ends[i] = e
                radii[i] = r

            # 6 vertices per segment: 2 triangles forming a quad
            # corners: (side=-1,end=0), (side=+1,end=0), (side=+1,end=1),
            #          (side=-1,end=0), (side=+1,end=1), (side=-1,end=1)
            data = np.empty((n * 6, 12), dtype=np.float32)

            for vi, (side, end_t) in enumerate(
                [
                    (-1, 0),
                    (1, 0),
                    (1, 1),
                    (-1, 0),
                    (1, 1),
                    (-1, 1),
                ]
            ):
                data[vi::6, 0:3] = starts
                data[vi::6, 3:6] = ends
                data[vi::6, 6] = radii
                data[vi::6, 7:10] = [br, bg, bb]
                data[vi::6, 10] = side
                data[vi::6, 11] = end_t

            vbo = self._ctx.buffer(data.tobytes())
            self._vao_segments = self._ctx.vertex_array(
                self._seg_prog,
                [
                    (
                        vbo,
                        "3f 3f 1f 3f 1f 1f",
                        "in_seg_start",
                        "in_seg_end",
                        "in_radius",
                        "in_color",
                        "in_side",
                        "in_end_t",
                    )
                ],
            )
            self._n_seg_verts = n * 6

        # Upload leaf data — 6 vertices per leaf billboard
        # Layout: position(3f) color(3f) side_x(1f) side_y(1f) size(1f) = 9 floats
        if self.geometry.leaves:
            lr = self.leaf_color[0] / 255.0
            lg = self.leaf_color[1] / 255.0
            lb = self.leaf_color[2] / 255.0
            leaf_size = 0.08

            n = len(self.geometry.leaves)
            leaf_pos = np.empty((n, 3), dtype=np.float32)
            for i, (pos, _) in enumerate(self.geometry.leaves):
                leaf_pos[i] = pos

            data = np.empty((n * 6, 9), dtype=np.float32)
            for vi, (sx, sy) in enumerate(
                [
                    (-1, -1),
                    (1, -1),
                    (1, 1),
                    (-1, -1),
                    (1, 1),
                    (-1, 1),
                ]
            ):
                data[vi::6, 0:3] = leaf_pos
                data[vi::6, 3:6] = [lr, lg, lb]
                data[vi::6, 6] = sx
                data[vi::6, 7] = sy
                data[vi::6, 8] = leaf_size

            vbo = self._ctx.buffer(data.tobytes())
            self._vao_leaves = self._ctx.vertex_array(
                self._leaf_prog,
                [(vbo, "3f 3f 1f 1f 1f", "in_position", "in_color", "in_side_x", "in_side_y", "in_size")],
            )
            self._n_leaf_verts = n * 6

    def _build_mvp(self) -> np.ndarray:
        aspect = self.width / max(self.height, 1)
        view = _look_at(self.camera.position, self.camera.target)
        proj = _perspective(self.camera.fov * np.pi / 180.0, aspect, 0.01, 500.0)
        return (proj @ view).astype(np.float32)

    def render(self) -> bytes:
        """Render to JPEG bytes (small for fast IPC transfer)."""
        return _image_to_jpeg(self.render_image())

    def render_png(self) -> bytes:
        """Render to PNG bytes (for file export)."""
        return _image_to_png(self.render_image())

    def render_image(self) -> Image.Image:
        """Render geometry and return a PIL Image."""
        self._ensure_fbo()
        assert self._ctx is not None
        assert self._seg_prog is not None
        assert self._leaf_prog is not None
        assert self._fbo is not None
        assert self._fbo_resolve is not None

        bg = (
            self.background_color[0] / 255.0,
            self.background_color[1] / 255.0,
            self.background_color[2] / 255.0,
            1.0,
        )

        self._fbo.use()
        self._ctx.clear(*bg)
        self._ctx.enable(moderngl.DEPTH_TEST)
        self._ctx.depth_func = "<"

        mvp = self._build_mvp()
        cam_pos = self.camera.position.astype(np.float32)

        # Draw segments
        if self._vao_segments is not None and self._n_seg_verts > 0:
            self._seg_prog["u_mvp"].write(mvp.T.tobytes())
            self._seg_prog["u_camera_pos"].value = tuple(cam_pos.tolist())
            self._seg_prog["u_fog_near"].value = self.camera.distance * 0.3
            self._seg_prog["u_fog_far"].value = self.camera.distance * 2.5
            self._seg_prog["u_bg_color"].value = bg[:3]
            self._vao_segments.render(moderngl.TRIANGLES, vertices=self._n_seg_verts)

        # Draw leaves
        if self._vao_leaves is not None and self._n_leaf_verts > 0:
            # Compute camera right/up for billboards
            forward = self.camera.target - self.camera.position
            fwd_len = np.linalg.norm(forward)
            if fwd_len > 1e-10:
                forward = forward / fwd_len
            else:
                forward = np.array([0, 0, -1], dtype=np.float64)
            cam_right = np.cross(forward, [0, 1, 0])
            cr_len = np.linalg.norm(cam_right)
            if cr_len < 1e-10:
                cam_right = np.array([1, 0, 0], dtype=np.float64)
            else:
                cam_right = cam_right / cr_len
            cam_up = np.cross(cam_right, forward)

            self._leaf_prog["u_mvp"].write(mvp.T.tobytes())
            self._leaf_prog["u_cam_right"].value = tuple(cam_right.astype(np.float32).tolist())
            self._leaf_prog["u_cam_up"].value = tuple(cam_up.astype(np.float32).tolist())
            self._leaf_prog["u_fog_near"].value = self.camera.distance * 0.3
            self._leaf_prog["u_fog_far"].value = self.camera.distance * 2.5
            self._leaf_prog["u_bg_color"].value = bg[:3]
            self._vao_leaves.render(moderngl.TRIANGLES, vertices=self._n_leaf_verts)

        # Resolve MSAA
        self._ctx.copy_framebuffer(self._fbo_resolve, self._fbo)
        self._fbo_resolve.use()
        data = self._fbo_resolve.read(components=3)
        img = Image.frombytes("RGB", (self.width, self.height), data)
        img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        return img


def _look_at(eye: np.ndarray, target: np.ndarray) -> np.ndarray:
    up = np.array([0.0, 1.0, 0.0])
    forward = target - eye
    fwd_len = np.linalg.norm(forward)
    if fwd_len < 1e-10:
        return np.eye(4, dtype=np.float32)
    forward = forward / fwd_len
    right = np.cross(forward, up)
    right_len = np.linalg.norm(right)
    if right_len < 1e-10:
        up = np.array([0.0, 0.0, 1.0])
        right = np.cross(forward, up)
        right_len = np.linalg.norm(right)
    right = right / right_len
    up = np.cross(right, forward)
    mat = np.eye(4, dtype=np.float32)
    mat[0, :3] = right
    mat[1, :3] = up
    mat[2, :3] = -forward
    mat[0, 3] = -np.dot(right, eye)
    mat[1, 3] = -np.dot(up, eye)
    mat[2, 3] = np.dot(forward, eye)
    return mat


def _perspective(fov: float, aspect: float, near: float, far: float) -> np.ndarray:
    f = 1.0 / np.tan(fov / 2.0)
    mat = np.zeros((4, 4), dtype=np.float32)
    mat[0, 0] = f / aspect
    mat[1, 1] = f
    mat[2, 2] = (far + near) / (near - far)
    mat[2, 3] = (2.0 * far * near) / (near - far)
    mat[3, 2] = -1.0
    return mat


def _image_to_jpeg(img: Image.Image, quality: int = 85) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def _image_to_png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

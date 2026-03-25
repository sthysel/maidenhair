"""Subprocess-based GL renderer.

Runs the moderngl context in a dedicated child process to avoid
OpenGL context conflicts with flet's Flutter engine.
"""

import io
import logging
import multiprocessing as mp
import queue
import threading
from dataclasses import dataclass
from typing import Any

import numpy as np
from PIL import Image

from maidenhair.core.turtle3d import Geometry

log = logging.getLogger(__name__)


@dataclass
class CameraState:
    azimuth: float = 0.0
    elevation: float = 0.3
    distance: float = 8.0
    target: tuple[float, float, float] = (0.0, 2.0, 0.0)
    fov: float = 45.0


@dataclass
class RenderRequest:
    width: int
    height: int
    camera: CameraState
    branch_color: tuple[int, int, int]
    leaf_color: tuple[int, int, int]
    background_color: tuple[int, int, int]
    segments: list[tuple[np.ndarray, np.ndarray, float]] | None = None
    leaves: list[tuple[np.ndarray, np.ndarray]] | None = None


def _worker_main(cmd_queue: mp.Queue, result_queue: mp.Queue) -> None:
    """Main loop for the render worker process."""
    try:
        from maidenhair.render.gl_viewport import GLViewport

        vp = GLViewport()
    except Exception as exc:
        result_queue.put(exc)
        return

    geometry: Geometry | None = None

    while True:
        try:
            req: RenderRequest | None = cmd_queue.get(timeout=30)
        except (EOFError, OSError):
            break
        except queue.Empty:
            continue

        if req is None:
            break

        try:
            if req.segments is not None or req.leaves is not None:
                geometry = Geometry()
                if req.segments is not None:
                    geometry.segments = req.segments
                if req.leaves is not None:
                    geometry.leaves = req.leaves
                vp.branch_color = req.branch_color
                vp.leaf_color = req.leaf_color
                vp.set_geometry(geometry)
            elif geometry is not None and vp.geometry is None:
                vp.set_geometry(geometry)

            vp.width = req.width
            vp.height = req.height
            vp.background_color = req.background_color

            vp.camera.azimuth = req.camera.azimuth
            vp.camera.elevation = req.camera.elevation
            vp.camera.distance = req.camera.distance
            vp.camera.target = np.array(req.camera.target, dtype=np.float64)
            vp.camera.fov = req.camera.fov
            vp.camera.update_position()

            img_bytes = vp.render()
            result_queue.put(img_bytes)
        except Exception as exc:
            # Send error back instead of crashing silently
            try:
                result_queue.put(exc)
            except Exception:
                pass


class GLProcessViewport:
    """Viewport proxy that renders via a child process with moderngl."""

    def __init__(self) -> None:
        self.width: int = 800
        self.height: int = 600
        self.branch_color: tuple[int, int, int] = (140, 90, 44)
        self.leaf_color: tuple[int, int, int] = (88, 180, 48)
        self.background_color: tuple[int, int, int] = (12, 22, 16)
        self.geometry: Geometry | None = None

        self._camera = CameraState()
        self._geometry_dirty = False
        self._lock = threading.Lock()
        self._alive = False

        self._start_worker()

    def _start_worker(self) -> None:
        ctx = mp.get_context("spawn")
        self._cmd_queue: mp.Queue[Any] = ctx.Queue(maxsize=4)
        self._result_queue: mp.Queue[Any] = ctx.Queue(maxsize=4)
        self._process = ctx.Process(
            target=_worker_main,
            args=(self._cmd_queue, self._result_queue),
            daemon=True,
        )
        self._process.start()
        self._alive = True

    def _ensure_alive(self) -> None:
        if self._process is not None and not self._process.is_alive():
            log.warning("GL worker died, restarting")
            self._start_worker()
            if self.geometry is not None:
                self._geometry_dirty = True

    def set_geometry(self, geometry: Geometry) -> None:
        self.geometry = geometry
        self._geometry_dirty = True
        if geometry.segments:
            centre = geometry.centre()
            mn, mx = geometry.bounding_box()
            extent = float(np.linalg.norm(mx - mn))
            self._camera.target = tuple(centre.tolist())
            self._camera.distance = max(extent * 1.5, 1.0)

    def rotate(self, dx: float, dy: float) -> None:
        self._camera.azimuth += dx * 0.005
        self._camera.elevation = float(
            np.clip(
                self._camera.elevation + dy * 0.005,
                -np.pi / 2 + 0.01,
                np.pi / 2 - 0.01,
            )
        )

    def zoom(self, delta: float) -> None:
        factor = 1.1 if delta > 0 else 0.9
        self._camera.distance = max(0.1, self._camera.distance * factor)

    def pan(self, dx: float, dy: float) -> None:
        az, el, dist = self._camera.azimuth, self._camera.elevation, self._camera.distance
        ce, se = np.cos(el), np.sin(el)
        sa, ca = np.sin(az), np.cos(az)
        cam_pos = np.array(self._camera.target) + np.array([dist * ce * sa, dist * se, dist * ce * ca])
        forward = np.array(self._camera.target) - cam_pos
        fwd_len = np.linalg.norm(forward)
        if fwd_len < 1e-10:
            return
        forward /= fwd_len
        right = np.cross(forward, [0.0, 1.0, 0.0])
        right_len = np.linalg.norm(right)
        if right_len < 1e-10:
            return
        right /= right_len
        up = np.cross(right, forward)
        sensitivity = dist * 0.002
        new_target = np.array(self._camera.target) + right * (-dx * sensitivity) + up * (dy * sensitivity)
        self._camera.target = tuple(new_target.tolist())

    def render(self) -> bytes:
        """Submit render request and return JPEG bytes. Thread-safe."""
        with self._lock:
            self._ensure_alive()

            req = RenderRequest(
                width=self.width,
                height=self.height,
                camera=CameraState(
                    azimuth=self._camera.azimuth,
                    elevation=self._camera.elevation,
                    distance=self._camera.distance,
                    target=self._camera.target,
                    fov=self._camera.fov,
                ),
                branch_color=self.branch_color,
                leaf_color=self.leaf_color,
                background_color=self.background_color,
                segments=self.geometry.segments if self._geometry_dirty and self.geometry else None,
                leaves=self.geometry.leaves if self._geometry_dirty and self.geometry else None,
            )
            self._geometry_dirty = False

            # Drain stale results
            while True:
                try:
                    self._result_queue.get_nowait()
                except (queue.Empty, OSError):
                    break

            try:
                self._cmd_queue.put(req, timeout=2.0)
            except (queue.Full, OSError):
                raise RuntimeError("GL worker queue full or dead")

            try:
                result = self._result_queue.get(timeout=10.0)
            except queue.Empty:
                raise RuntimeError("GL worker timed out")

            if isinstance(result, Exception):
                raise result
            return result

    def render_png(self) -> bytes:
        jpeg_bytes = self.render()
        img = Image.open(io.BytesIO(jpeg_bytes))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    def shutdown(self) -> None:
        try:
            self._cmd_queue.put_nowait(None)
            self._process.join(timeout=2)
        except Exception:
            pass
        finally:
            if self._process.is_alive():
                self._process.kill()
            try:
                self._cmd_queue.close()
                self._result_queue.close()
            except Exception:
                pass

    def __del__(self) -> None:
        self.shutdown()

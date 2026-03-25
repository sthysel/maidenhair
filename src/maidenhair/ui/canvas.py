"""Flet canvas wrapping the GL or software rasteriser viewport."""

import asyncio
import time

import flet as ft

from maidenhair.core.grammar import LSystem
from maidenhair.core.parametric import tokenise
from maidenhair.core.presets import PresetConfig
from maidenhair.core.turtle3d import Geometry, interpret

_DRAG_THROTTLE = 0.03


def _create_viewport() -> tuple:  # type: ignore[type-arg]
    """Create a viewport — prefer subprocess GL, fall back to software."""
    try:
        from maidenhair.render.gl_process import GLProcessViewport

        vp = GLProcessViewport()
        vp.render()
        return vp, "OpenGL"
    except Exception:
        from maidenhair.render.viewport import Viewport

        return Viewport(), "PIL"


class LSystemCanvas(ft.Container):
    """Interactive 3D canvas with FPS and renderer labels."""

    def __init__(self) -> None:
        self.viewport, self.renderer_name = _create_viewport()
        self._image = ft.Image(
            src="",
            fit=ft.BoxFit.FILL,
            expand=True,
            gapless_playback=True,  # keep old frame visible while new one loads
        )

        self._status_label = ft.Text(
            value=self.renderer_name,
            size=11,
            color=ft.Colors.with_opacity(0.5, ft.Colors.WHITE),
        )
        self._spinner = ft.ProgressRing(visible=False)
        self._last_x: float = 0
        self._last_y: float = 0
        self._preset: PresetConfig | None = None
        self._lsystem: LSystem | None = None
        self._iterations: int = 4
        self._seed: int | None = None
        self._last_render_time: float = 0
        self._render_pending: bool = False
        self._resize_task: asyncio.Task[None] | None = None
        self._fps: float = 0
        self._frame_count: int = 0
        self._fps_window_start: float = time.monotonic()

        gesture = ft.GestureDetector(
            content=ft.Stack(
                controls=[
                    self._image,
                    ft.Container(content=self._spinner, alignment=ft.Alignment(0, 0)),
                    ft.Container(
                        content=self._status_label,
                        padding=ft.padding.only(left=8, bottom=4),
                        alignment=ft.Alignment(-1, 1),
                    ),
                ],
                expand=True,
            ),
            on_pan_start=self._on_pan_start,
            on_pan_update=self._on_pan_update,
            on_scroll=self._on_scroll,
            expand=True,
        )

        super().__init__(
            content=gesture,
            expand=True,
            bgcolor=ft.Colors.BLACK,
            on_size_change=self._on_resize,
        )

    def _update_fps(self) -> None:
        self._frame_count += 1
        now = time.monotonic()
        elapsed = now - self._fps_window_start
        if elapsed >= 0.5:
            self._fps = self._frame_count / elapsed
            self._frame_count = 0
            self._fps_window_start = now
            self._status_label.value = f"{self.renderer_name}  {self._fps:.0f} fps"
            if self.page:
                self._status_label.update()

    async def _on_resize(self, e: ft.LayoutSizeChangeEvent) -> None:
        w, h = int(e.width), int(e.height)
        if w < 10 or h < 10:
            return
        if w == self.viewport.width and h == self.viewport.height:
            return
        self.viewport.width = w
        self.viewport.height = h
        if self._resize_task and not self._resize_task.done():
            self._resize_task.cancel()
        self._resize_task = asyncio.create_task(self._debounced_resize_render())

    async def _debounced_resize_render(self) -> None:
        await asyncio.sleep(0.05)
        await self._render_frame()

    async def set_preset(self, preset: PresetConfig, iterations: int | None = None) -> None:
        self._preset = preset
        self._lsystem = preset.to_lsystem()
        self._iterations = iterations if iterations is not None else preset.params.iterations_default
        self.viewport.branch_color = tuple(preset.display.branch_color)  # type: ignore[assignment]
        self.viewport.leaf_color = tuple(preset.display.leaf_color)  # type: ignore[assignment]
        self.viewport.background_color = tuple(preset.display.background_color)  # type: ignore[assignment]
        await self.recompute()

    async def recompute(self) -> None:
        if self._lsystem is None or self._preset is None:
            return
        self._spinner.visible = True
        if self.page:
            self.page.update()
        geometry = await asyncio.to_thread(self._compute_geometry)
        self.viewport.set_geometry(geometry)
        await self._render_frame()
        self._spinner.visible = False
        if self.page:
            self.page.update()

    def _compute_geometry(self) -> Geometry:
        assert self._lsystem is not None
        assert self._preset is not None
        derivation = self._lsystem.derive(self._iterations, seed=self._seed)
        symbols = tokenise(derivation)
        return interpret(
            symbols,
            step_length=self._preset.params.step_length,
            angle_default=self._preset.params.angle_default,
            radius_start=self._preset.params.radius_start,
            radius_ratio=self._preset.params.radius_ratio,
            tropism_weight=self._preset.params.tropism_weight,
        )

    async def _render_frame(self) -> None:
        try:
            img_bytes = await asyncio.to_thread(self.viewport.render)
        except Exception as exc:
            self._status_label.value = f"{self.renderer_name}  error: {exc}"
            if self.page:
                self._status_label.update()
            return

        # Pass raw bytes directly — no base64 encoding needed
        self._image.src = img_bytes
        self._last_render_time = time.monotonic()
        self._update_fps()
        if self.page:
            self._image.update()

    async def _throttled_render(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_render_time
        if elapsed < _DRAG_THROTTLE:
            if self._render_pending:
                return
            self._render_pending = True
            await asyncio.sleep(_DRAG_THROTTLE - elapsed)
            self._render_pending = False
        await self._render_frame()

    def _on_pan_start(self, e: ft.DragStartEvent) -> None:
        self._last_x = e.local_position.x
        self._last_y = e.local_position.y

    async def _on_pan_update(self, e: ft.DragUpdateEvent) -> None:
        dx = e.local_position.x - self._last_x
        dy = e.local_position.y - self._last_y
        self._last_x = e.local_position.x
        self._last_y = e.local_position.y
        self.viewport.rotate(dx, dy)
        await self._throttled_render()

    async def _on_scroll(self, e: ft.ScrollEvent) -> None:
        self.viewport.zoom(e.scroll_delta.y)
        await self._throttled_render()

    async def set_iterations(self, n: int) -> None:
        self._iterations = n
        await self.recompute()

    async def set_seed(self, seed: int | None) -> None:
        self._seed = seed
        await self.recompute()

    async def update_params(
        self,
        *,
        step_length: float | None = None,
        angle_default: float | None = None,
        radius_start: float | None = None,
        radius_ratio: float | None = None,
        tropism_weight: float | None = None,
    ) -> None:
        if self._preset is None:
            return
        if step_length is not None:
            self._preset.params.step_length = step_length
        if angle_default is not None:
            self._preset.params.angle_default = angle_default
        if radius_start is not None:
            self._preset.params.radius_start = radius_start
        if radius_ratio is not None:
            self._preset.params.radius_ratio = radius_ratio
        if tropism_weight is not None:
            self._preset.params.tropism_weight = tropism_weight
        await self.recompute()

    async def set_grammar(self, axiom: str, rules: dict[str, str]) -> None:
        """Update just the grammar (axiom + rules) and recompute.

        Used by the live editor. Keeps the current parameters and display settings.
        """
        self._lsystem = LSystem(axiom=axiom, rules=rules)
        if self._preset is not None:
            self._preset.grammar.axiom = axiom
            self._preset.grammar.rules = rules
        await self.recompute()

    def reset_camera(self) -> None:
        if self.viewport.geometry:
            self.viewport.set_geometry(self.viewport.geometry)

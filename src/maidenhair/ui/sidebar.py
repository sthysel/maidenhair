"""Sidebar controls — parameters, display, and export."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Any

import flet as ft

from maidenhair.core.palette import BACKGROUND_COLORS, BRANCH_COLORS, LEAF_COLORS, PALETTE
from maidenhair.core.presets import PresetConfig, list_bundled_presets, load_preset
from maidenhair.render.export import export_mesh

if TYPE_CHECKING:
    from maidenhair.ui.canvas import LSystemCanvas


def _rgb_to_palette_name(rgb: list[int], candidates: list[str]) -> str:
    """Find the closest palette name for an RGB value."""
    best_name = candidates[0]
    best_dist = float("inf")
    for name in candidates:
        pr, pg, pb = PALETTE[name]
        dist = (pr - rgb[0]) ** 2 + (pg - rgb[1]) ** 2 + (pb - rgb[2]) ** 2
        if dist < best_dist:
            best_dist = dist
            best_name = name
    return best_name


class Sidebar(ft.Container):
    """Right sidebar with preset selector, parameter sliders, display, and export."""

    def __init__(self, canvas: LSystemCanvas) -> None:
        self._canvas = canvas
        self._debounce_task: asyncio.Task[None] | None = None

        # Preset selector
        presets = list_bundled_presets()
        self._preset_names = sorted(presets.keys())
        self._preset_dropdown = ft.Dropdown(
            label="Preset",
            options=[ft.dropdown.Option(name) for name in self._preset_names],
            value=self._preset_names[0] if self._preset_names else None,
            on_select=self._on_preset_change,
        )

        # Iterations stepper
        self._iterations_field = ft.TextField(
            label="Iterations",
            value="4",
            keyboard_type=ft.KeyboardType.NUMBER,
            width=120,
            on_submit=self._on_iterations_change,
        )
        self._iter_up = ft.IconButton(icon=ft.Icons.ADD, on_click=self._iter_increment)
        self._iter_down = ft.IconButton(icon=ft.Icons.REMOVE, on_click=self._iter_decrement)

        # Geometry parameter sliders
        self._step_length = self._make_slider("Step Length", 0.1, 3.0, 1.0)
        self._radius_start = self._make_slider("Radius", 0.01, 0.2, 0.05)
        self._radius_ratio = self._make_slider("Radius Ratio", 0.3, 1.0, 0.75)
        self._angle_default = self._make_slider("Default Angle", 5.0, 90.0, 25.0)
        self._tropism_weight = self._make_slider("Tropism", 0.0, 0.5, 0.12)

        # Display colour dropdowns
        self._leaf_color_dd = ft.Dropdown(
            label="Leaf colour",
            options=[ft.dropdown.Option(name) for name in LEAF_COLORS],
            value="light-green",
            on_select=self._on_color_change,
        )
        self._branch_color_dd = ft.Dropdown(
            label="Branch colour",
            options=[ft.dropdown.Option(name) for name in BRANCH_COLORS],
            value="dark-bark",
            on_select=self._on_color_change,
        )
        self._bg_color_dd = ft.Dropdown(
            label="Background",
            options=[ft.dropdown.Option(name) for name in BACKGROUND_COLORS],
            value="forest-night",
            on_select=self._on_color_change,
        )

        # Export buttons
        self._export_obj = ft.ElevatedButton(
            content=ft.Text(value="Export OBJ"), on_click=lambda _: self._export("obj")
        )
        self._export_glb = ft.ElevatedButton(
            content=ft.Text(value="Export GLB"), on_click=lambda _: self._export("glb")
        )
        self._export_ply = ft.ElevatedButton(
            content=ft.Text(value="Export PLY"), on_click=lambda _: self._export("ply")
        )
        self._export_png = ft.ElevatedButton(
            content=ft.Text(value="Export PNG"), on_click=lambda _: self._export("png")
        )

        super().__init__(
            content=ft.Column(
                controls=[
                    ft.Text(value="Preset", size=16, weight=ft.FontWeight.BOLD),
                    self._preset_dropdown,
                    ft.Divider(),
                    ft.Text(value="Iterations", size=16, weight=ft.FontWeight.BOLD),
                    ft.Row(controls=[self._iter_down, self._iterations_field, self._iter_up]),
                    ft.Divider(),
                    ft.Text(value="Geometry", size=16, weight=ft.FontWeight.BOLD),
                    self._step_length["row"],
                    self._radius_start["row"],
                    self._radius_ratio["row"],
                    self._angle_default["row"],
                    self._tropism_weight["row"],
                    ft.Divider(),
                    ft.Text(value="Display", size=16, weight=ft.FontWeight.BOLD),
                    self._leaf_color_dd,
                    self._branch_color_dd,
                    self._bg_color_dd,
                    ft.Divider(),
                    ft.Text(value="Export", size=16, weight=ft.FontWeight.BOLD),
                    ft.Row(controls=[self._export_obj, self._export_glb], wrap=True),
                    ft.Row(controls=[self._export_ply, self._export_png], wrap=True),
                ],
                scroll=ft.ScrollMode.AUTO,
                spacing=8,
            ),
            width=320,
            padding=16,
        )

    def _make_slider(self, label: str, min_val: float, max_val: float, value: float) -> dict[str, Any]:
        slider = ft.Slider(
            min=min_val,
            max=max_val,
            value=value,
            divisions=100,
            label=f"{value:.2f}",
            on_change_end=self._on_slider_change,
            expand=True,
        )
        label_text = ft.Text(value=label, size=12)
        value_text = ft.Text(value=f"{value:.2f}", size=12)
        row = ft.Row(controls=[label_text, slider, value_text], spacing=4)
        return {"slider": slider, "text": label_text, "value_text": value_text, "row": row}

    # --- Preset loading ---

    async def load_default_preset(self) -> None:
        if self._preset_names:
            presets = list_bundled_presets()
            name = self._preset_names[0]
            preset = load_preset(presets[name])
            self._update_controls_from_preset(preset)
            await self._canvas.set_preset(preset)

    async def _on_preset_change(self, _e: ft.ControlEvent) -> None:
        name = self._preset_dropdown.value
        if name is None:
            return
        presets = list_bundled_presets()
        if name in presets:
            preset = load_preset(presets[name])
            self._update_controls_from_preset(preset)
            await self._canvas.set_preset(preset)

    def _update_controls_from_preset(self, preset: PresetConfig) -> None:
        self._step_length["slider"].value = preset.params.step_length
        self._step_length["value_text"].value = f"{preset.params.step_length:.2f}"
        self._radius_start["slider"].value = preset.params.radius_start
        self._radius_start["value_text"].value = f"{preset.params.radius_start:.2f}"
        self._radius_ratio["slider"].value = preset.params.radius_ratio
        self._radius_ratio["value_text"].value = f"{preset.params.radius_ratio:.2f}"
        self._angle_default["slider"].value = preset.params.angle_default
        self._angle_default["value_text"].value = f"{preset.params.angle_default:.2f}"
        self._tropism_weight["slider"].value = preset.params.tropism_weight
        self._tropism_weight["value_text"].value = f"{preset.params.tropism_weight:.2f}"
        self._iterations_field.value = str(preset.params.iterations_default)

        self._leaf_color_dd.value = _rgb_to_palette_name(preset.display.leaf_color, LEAF_COLORS)
        self._branch_color_dd.value = _rgb_to_palette_name(preset.display.branch_color, BRANCH_COLORS)
        self._bg_color_dd.value = _rgb_to_palette_name(preset.display.background_color, BACKGROUND_COLORS)

    # --- Sliders ---

    async def _on_slider_change(self, _e: ft.ControlEvent) -> None:
        sliders = [
            self._step_length,
            self._radius_start,
            self._radius_ratio,
            self._angle_default,
            self._tropism_weight,
        ]
        for info in sliders:
            info["value_text"].value = f"{info['slider'].value:.2f}"
        if self._debounce_task and not self._debounce_task.done():
            self._debounce_task.cancel()
        self._debounce_task = asyncio.create_task(self._debounced_update())

    async def _debounced_update(self) -> None:
        await asyncio.sleep(0.3)
        await self._canvas.update_params(
            step_length=self._step_length["slider"].value,
            angle_default=self._angle_default["slider"].value,
            radius_start=self._radius_start["slider"].value,
            radius_ratio=self._radius_ratio["slider"].value,
            tropism_weight=self._tropism_weight["slider"].value,
        )

    # --- Iterations ---

    async def _on_iterations_change(self, _e: ft.ControlEvent) -> None:
        try:
            n = int(self._iterations_field.value or "1")
            n = max(1, min(10, n))
            self._iterations_field.value = str(n)
            await self._canvas.set_iterations(n)
        except (ValueError, TypeError):
            pass

    async def _iter_increment(self, _e: ft.ControlEvent) -> None:
        try:
            n = int(self._iterations_field.value or "1") + 1
            n = min(10, n)
            self._iterations_field.value = str(n)
            if self.page:
                self._iterations_field.update()
            await self._canvas.set_iterations(n)
        except (ValueError, TypeError):
            pass

    async def _iter_decrement(self, _e: ft.ControlEvent) -> None:
        try:
            n = int(self._iterations_field.value or "1") - 1
            n = max(1, n)
            self._iterations_field.value = str(n)
            if self.page:
                self._iterations_field.update()
            await self._canvas.set_iterations(n)
        except (ValueError, TypeError):
            pass

    # --- Display ---

    async def _on_color_change(self, _e: ft.ControlEvent) -> None:
        lc_name = self._leaf_color_dd.value or "light-green"
        bc_name = self._branch_color_dd.value or "dark-bark"
        bg_name = self._bg_color_dd.value or "forest-night"

        lc = PALETTE.get(lc_name, (75, 175, 55))
        bc = PALETTE.get(bc_name, (30, 15, 8))
        bg = PALETTE.get(bg_name, (12, 22, 16))

        self._canvas.viewport.branch_color = bc  # type: ignore[assignment]
        self._canvas.viewport.leaf_color = lc  # type: ignore[assignment]
        self._canvas.viewport.background_color = bg  # type: ignore[assignment]

        if self._canvas._preset is not None:
            self._canvas._preset.display.branch_color = list(bc)
            self._canvas._preset.display.leaf_color = list(lc)
            self._canvas._preset.display.background_color = list(bg)

        await self._canvas.recompute()

    # --- Export ---

    def _export(self, fmt: str) -> None:
        if self._canvas.viewport.geometry is None:
            return
        if fmt == "png":
            png_bytes = self._canvas.viewport.render_png()
            path = Path("maidenhair_export.png")
            path.write_bytes(png_bytes)
        else:
            path = Path(f"maidenhair_export.{fmt}")
            export_mesh(
                self._canvas.viewport.geometry,
                path,
                file_format=fmt,
                branch_color=self._canvas.viewport.branch_color,
                leaf_color=self._canvas.viewport.leaf_color,
            )
        if self.page:
            snack = ft.SnackBar(content=ft.Text(value=f"Exported to {path}"), open=True)
            self.page.overlay.append(snack)
            self.page.update()

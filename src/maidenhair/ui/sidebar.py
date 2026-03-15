"""Sidebar controls for L-system parameter adjustment."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Any

import flet as ft

from maidenhair.core.presets import PresetConfig, list_bundled_presets, load_preset
from maidenhair.render.export import export_mesh

if TYPE_CHECKING:
    from maidenhair.ui.canvas import LSystemCanvas


class Sidebar(ft.Container):
    """Right sidebar with preset selector, parameter sliders, and export buttons."""

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
            width=280,
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
        self._step_length = self._make_slider("Step Length", 0.1, 3.0, 0.8)
        self._radius_start = self._make_slider("Radius", 0.01, 0.2, 0.05)
        self._radius_ratio = self._make_slider("Radius Ratio", 0.3, 1.0, 0.75)
        self._angle_default = self._make_slider("Default Angle", 5.0, 90.0, 25.0)
        self._tropism_weight = self._make_slider("Tropism", 0.0, 0.5, 0.12)

        # Display controls
        self._branch_color = ft.TextField(
            label="Branch RGB", value="30,10,2", width=280, on_submit=self._on_color_change
        )
        self._leaf_color = ft.TextField(label="Leaf RGB", value="88,155,48", width=280, on_submit=self._on_color_change)

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
                    ft.Text(value="Presets", size=16, weight=ft.FontWeight.BOLD),
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
                    self._branch_color,
                    self._leaf_color,
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

    async def load_default_preset(self) -> None:
        """Load the first available preset."""
        if self._preset_names:
            presets = list_bundled_presets()
            name = self._preset_names[0]
            preset = load_preset(presets[name])
            self._update_sliders_from_preset(preset)
            await self._canvas.set_preset(preset)

    async def _on_preset_change(self, e: ft.ControlEvent) -> None:
        name = self._preset_dropdown.value
        if name is None:
            return
        presets = list_bundled_presets()
        if name in presets:
            preset = load_preset(presets[name])
            self._update_sliders_from_preset(preset)
            await self._canvas.set_preset(preset)

    def _update_sliders_from_preset(self, preset: PresetConfig) -> None:
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

        bc = preset.display.branch_color
        lc = preset.display.leaf_color
        self._branch_color.value = f"{bc[0]},{bc[1]},{bc[2]}"
        self._leaf_color.value = f"{lc[0]},{lc[1]},{lc[2]}"

    async def _on_slider_change(self, _e: ft.ControlEvent) -> None:
        # Update value display
        sliders = [
            self._step_length,
            self._radius_start,
            self._radius_ratio,
            self._angle_default,
            self._tropism_weight,
        ]
        for info in sliders:
            info["value_text"].value = f"{info['slider'].value:.2f}"

        # Debounce: cancel previous recompute
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

    async def _on_iterations_change(self, e: ft.ControlEvent) -> None:
        try:
            n = int(self._iterations_field.value or "1")
            n = max(1, min(8, n))
            self._iterations_field.value = str(n)
            await self._canvas.set_iterations(n)
        except (ValueError, TypeError):
            pass

    async def _iter_increment(self, _e: ft.ControlEvent) -> None:
        try:
            current = self._iterations_field.value or "1"
            n = int(current) + 1
            n = min(8, n)
            self._iterations_field.value = str(n)
            if self.page:
                self._iterations_field.update()
            await self._canvas.set_iterations(n)
        except (ValueError, TypeError):
            pass

    async def _iter_decrement(self, _e: ft.ControlEvent) -> None:
        try:
            current = self._iterations_field.value or "1"
            n = int(current) - 1
            n = max(1, n)
            self._iterations_field.value = str(n)
            if self.page:
                self._iterations_field.update()
            await self._canvas.set_iterations(n)
        except (ValueError, TypeError):
            pass

    async def _on_color_change(self, _e: ft.ControlEvent) -> None:
        try:
            bc_val = self._branch_color.value or ""
            lc_val = self._leaf_color.value or ""
            bc = tuple(int(x.strip()) for x in bc_val.split(","))
            lc = tuple(int(x.strip()) for x in lc_val.split(","))
            if len(bc) == 3 and len(lc) == 3:
                self._canvas.viewport.branch_color = bc  # type: ignore[assignment]
                self._canvas.viewport.leaf_color = lc  # type: ignore[assignment]
                await self._canvas._render_frame()
        except (ValueError, TypeError):
            pass

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

"""Top toolbar for Maidenhair."""

import random
from typing import TYPE_CHECKING

import flet as ft

if TYPE_CHECKING:
    from maidenhair.ui.canvas import LSystemCanvas


class Toolbar(ft.Container):
    """Top bar with app title, randomise, and reset camera buttons."""

    def __init__(self, canvas: LSystemCanvas) -> None:
        self._canvas = canvas

        title = ft.Text(
            value="Maidenhair",
            size=20,
            weight=ft.FontWeight.BOLD,
        )

        randomise_btn = ft.ElevatedButton(
            content=ft.Text(value="Randomise"),
            icon=ft.Icons.SHUFFLE,
            on_click=self._on_randomise,
        )

        reset_camera_btn = ft.ElevatedButton(
            content=ft.Text(value="Reset Camera"),
            icon=ft.Icons.CENTER_FOCUS_STRONG,
            on_click=self._on_reset_camera,
        )

        super().__init__(
            content=ft.Row(
                controls=[
                    title,
                    ft.Container(expand=True),
                    randomise_btn,
                    reset_camera_btn,
                ],
                alignment=ft.MainAxisAlignment.START,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(horizontal=16, vertical=8),
            bgcolor=ft.Colors.SURFACE,
        )

    async def _on_randomise(self, _e: ft.ControlEvent) -> None:
        new_seed = random.randint(0, 2**31)
        await self._canvas.set_seed(new_seed)

    async def _on_reset_camera(self, _e: ft.ControlEvent) -> None:
        self._canvas.reset_camera()
        await self._canvas._render_frame()

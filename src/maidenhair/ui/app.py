"""Flet application entry point for Maidenhair."""

from __future__ import annotations

import flet as ft

from maidenhair.ui.canvas import LSystemCanvas
from maidenhair.ui.sidebar import Sidebar
from maidenhair.ui.toolbar import Toolbar


def main() -> None:
    """Launch the Maidenhair flet application."""
    ft.app(target=_app)


async def _app(page: ft.Page) -> None:
    page.title = "Maidenhair — L-System Botanical Explorer"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 0

    canvas = LSystemCanvas()
    sidebar = Sidebar(canvas=canvas)
    toolbar = Toolbar(canvas=canvas)

    page.add(  # type: ignore[arg-type]
        ft.Column(
            controls=[
                toolbar,
                ft.Row(
                    controls=[
                        canvas,
                        ft.VerticalDivider(width=1),
                        sidebar,
                    ],
                    expand=True,
                    spacing=0,
                ),
            ],
            expand=True,
            spacing=0,
        )
    )

    # Load default preset
    await sidebar.load_default_preset()

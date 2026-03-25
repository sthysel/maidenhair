"""Flet application entry point for Maidenhair."""

import flet as ft

from maidenhair.ui.canvas import LSystemCanvas
from maidenhair.ui.editor_page import EditorPage
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
    editor = EditorPage(canvas=canvas)

    sidebar_panel = ft.Container(content=sidebar, visible=True)
    editor_panel = ft.Container(content=editor, expand=2, visible=False)

    def switch_page(e: ft.ControlEvent) -> None:
        idx = e.control.selected_index
        sidebar_panel.visible = idx == 0
        editor_panel.visible = idx == 1
        page.update()

    rail = ft.NavigationRail(
        destinations=[
            ft.NavigationRailDestination(
                icon=ft.Icons.PARK,
                selected_icon=ft.Icons.PARK,
                label="Viewport",
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.EDIT_NOTE,
                selected_icon=ft.Icons.EDIT_NOTE,
                label="Grammar",
            ),
        ],
        selected_index=0,
        label_type=ft.NavigationRailLabelType.ALL,
        min_width=72,
        on_change=switch_page,
    )

    page.add(  # type: ignore[arg-type]
        ft.Column(
            controls=[
                toolbar,
                ft.Row(
                    controls=[
                        rail,
                        ft.VerticalDivider(width=1),
                        canvas,
                        ft.VerticalDivider(width=1),
                        sidebar_panel,
                        editor_panel,
                    ],
                    expand=True,
                    spacing=0,
                ),
            ],
            expand=True,
            spacing=0,
        )
    )

    await sidebar.load_default_preset()
    editor.populate_from_preset()

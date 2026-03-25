"""Grammar editor page — full L-system editor with live preview."""

import asyncio
import importlib.resources
from typing import TYPE_CHECKING

import flet as ft

from maidenhair.core.presets import list_bundled_presets, load_preset

if TYPE_CHECKING:
    from maidenhair.ui.canvas import LSystemCanvas

_EDITOR_DEBOUNCE = 0.6


def _load_help_text() -> str:
    try:
        ref = importlib.resources.files("maidenhair.help").joinpath("l-systems-help.md")
        return ref.read_text(encoding="utf-8")
    except Exception:
        return "# Help\n\nHelp file not found."


class EditorPage(ft.Container):
    """Full grammar editor. Uses CrossAxisAlignment.STRETCH so all children fill width."""

    def __init__(self, canvas: LSystemCanvas) -> None:
        self._canvas = canvas
        self._debounce_task: asyncio.Task[None] | None = None

        presets = list_bundled_presets()
        self._preset_names = sorted(presets.keys())

        self._preset_dd = ft.Dropdown(
            label="Load preset into editor",
            options=[ft.dropdown.Option(name) for name in self._preset_names],
            on_select=self._on_load_preset,
        )

        self._axiom = ft.TextField(
            label="Axiom",
            value="",
            multiline=True,
            min_lines=4,
            max_lines=8,
            text_size=14,
            text_style=ft.TextStyle(font_family="monospace"),
            on_change=self._on_edit,
        )

        self._rules = ft.TextField(
            label="Production rules  (one per line:  X = replacement)",
            value="",
            multiline=True,
            min_lines=12,
            max_lines=40,
            text_size=14,
            text_style=ft.TextStyle(font_family="monospace"),
            on_change=self._on_edit,
        )

        self._status = ft.Text(value="", size=12, color=ft.Colors.RED_300)

        self._derivation_preview = ft.TextField(
            label="Derivation preview (read-only)",
            value="",
            read_only=True,
            multiline=True,
            min_lines=3,
            max_lines=6,
            text_size=12,
            text_style=ft.TextStyle(font_family="monospace", color=ft.Colors.YELLOW_400),
        )

        self._help_text = _load_help_text()
        self._help_added = False

        help_btn = ft.IconButton(
            icon=ft.Icons.HELP_OUTLINE,
            tooltip="L-Systems reference",
            on_click=self._show_help,
        )

        header = ft.Row(
            controls=[
                ft.Text(value="Grammar Editor", size=18, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                help_btn,
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        super().__init__(
            content=ft.Column(
                controls=[
                    header,
                    self._preset_dd,
                    self._axiom,
                    self._rules,
                    self._status,
                    self._derivation_preview,
                ],
                spacing=6,
                expand=True,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                scroll=ft.ScrollMode.AUTO,
            ),
            expand=True,
            padding=10,
        )

    def populate_from_preset(self, preset_name: str | None = None) -> None:
        if preset_name is None:
            preset_name = self._preset_names[0] if self._preset_names else None
        if preset_name is None:
            return
        presets = list_bundled_presets()
        if preset_name not in presets:
            return
        preset = load_preset(presets[preset_name])
        self._axiom.value = preset.grammar.axiom
        self._rules.value = "\n".join(f"{k} = {v}" for k, v in preset.grammar.rules.items())
        self._preset_dd.value = preset_name
        self._status.value = ""

    async def _on_load_preset(self, _e: ft.ControlEvent) -> None:
        name = self._preset_dd.value
        if name:
            self.populate_from_preset(name)
            if self.page:
                self.page.update()
            await self._apply_grammar()

    async def _on_edit(self, _e: ft.ControlEvent) -> None:
        if self._debounce_task and not self._debounce_task.done():
            self._debounce_task.cancel()
        self._debounce_task = asyncio.create_task(self._debounced_apply())

    async def _debounced_apply(self) -> None:
        await asyncio.sleep(_EDITOR_DEBOUNCE)
        await self._apply_grammar()

    def _parse_rules(self) -> dict[str, str] | None:
        rules: dict[str, str] = {}
        text = self._rules.value or ""
        for line in text.strip().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                return None
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if len(key) != 1:
                return None
            rules[key] = value
        return rules

    async def _apply_grammar(self) -> None:
        axiom = (self._axiom.value or "").strip()
        if not axiom:
            self._status.value = "Axiom is empty"
            if self.page:
                self._status.update()
            return

        rules = self._parse_rules()
        if rules is None:
            self._status.value = "Invalid rule  (format: X = replacement)"
            if self.page:
                self._status.update()
            return

        self._status.value = ""
        if self.page:
            self._status.update()

        try:
            await self._canvas.set_grammar(axiom, rules)
            if self._canvas._lsystem:
                d = self._canvas._lsystem.derive(
                    min(self._canvas._iterations, 4),
                    seed=self._canvas._seed,
                )
                preview = d[:500]
                if len(d) > 500:
                    preview += f"... ({len(d):,} chars total)"
                self._derivation_preview.value = preview
                if self.page:
                    self._derivation_preview.update()
        except Exception as exc:
            self._status.value = str(exc)[:120]
            if self.page:
                self._status.update()

    async def _show_help(self, _e: ft.ControlEvent) -> None:
        if not self.page:
            return

        def close_help(_e: ft.ControlEvent) -> None:
            bs.open = False
            if self.page:
                self.page.update()

        bs = ft.BottomSheet(
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Text(
                                    value="L-Systems Reference",
                                    size=20,
                                    weight=ft.FontWeight.BOLD,
                                ),
                                ft.Container(expand=True),
                                ft.IconButton(icon=ft.Icons.CLOSE, on_click=close_help),
                            ],
                        ),
                        ft.Markdown(
                            value=self._help_text,
                            selectable=True,
                            extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                            expand=True,
                        ),
                    ],
                    expand=True,
                    scroll=ft.ScrollMode.AUTO,
                ),
                padding=20,
                expand=True,
            ),
            open=True,
            fullscreen=True,
        )
        self.page.overlay.append(bs)
        self.page.update()

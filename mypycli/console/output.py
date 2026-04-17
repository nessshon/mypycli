from __future__ import annotations

import json
from typing import TYPE_CHECKING

from mypycli.console.ansi import (
    box_chars,
    colorize_text,
    render_color_text,
    visible_len,
)
from mypycli.types import BoxStyle, Color, ColorText, Command

if TYPE_CHECKING:
    from collections.abc import Sequence


class ConsoleOutput:
    """Mixin providing formatted terminal output: text, tables, panels, help listings and JSON."""

    @staticmethod
    def print(text: str = "", color: Color | None = None) -> None:
        """Print a line of text, optionally wrapped in an ANSI color.

        :param text: Line of text to print.
        :param color: When ``None``, the text is printed without any color wrapping.
        """
        if color is not None:
            text = colorize_text(text, color)
        print(text)

    @staticmethod
    def print_table(
        rows: list[list[str | ColorText]],
        *,
        header: str | ColorText | None = None,
        footer: str | ColorText | None = None,
        style: BoxStyle | None = None,
    ) -> None:
        """Print a table with auto-sized columns; the first row is treated as a header when borders are drawn.

        :param rows: Table rows; each row is a list of string or ``ColorText`` cells.
        :param header: Title shown in the top border (boxed style only).
        :param footer: Caption shown in the bottom border (boxed style only).
        :param style: Box-drawing style; ``None`` prints a plain borderless table.
        """
        if not rows:
            return

        rendered_rows: list[list[str]] = [[str(render_color_text(cell)) for cell in row] for row in rows]

        col_count = max(len(row) for row in rendered_rows)
        col_widths = [
            max((visible_len(r[i]) for r in rendered_rows if i < len(r)), default=0) for i in range(col_count)
        ]

        header_text = str(render_color_text(header)) if header else ""
        footer_text = str(render_color_text(footer)) if footer else ""

        if style is not None:
            ConsoleOutput._print_table_boxed(rendered_rows, col_widths, style, header_text, footer_text)
        else:
            ConsoleOutput._print_table_plain(rendered_rows, col_widths, header_text, footer_text)

    @staticmethod
    def print_panel(
        items: Sequence[tuple[str | ColorText, str | ColorText] | tuple[()]] | None = None,
        *,
        header: str | ColorText | None = None,
        footer: str | ColorText | None = None,
        style: BoxStyle = BoxStyle.ROUNDED,
    ) -> None:
        """Print a bordered panel listing key-value pairs with aligned labels.

        :param items: Sequence of ``(label, value)`` tuples; an empty tuple inserts a blank separator line.
        :param header: Optional title rendered inside the top border.
        :param footer: Optional caption rendered inside the bottom border.
        :param style: Box-drawing style used for the panel borders.
        """
        tl, tr, bl, br, h, v, *_ = box_chars(style.name)
        rendered_items = items or []

        formatted: list[str] = []
        label_width = 0
        for item in rendered_items:
            if not item:
                continue
            label_width = max(label_width, visible_len(str(render_color_text(item[0]))))

        for item in rendered_items:
            if not item:
                formatted.append("")
            else:
                label = str(render_color_text(item[0]))
                value = str(render_color_text(item[1]))
                pad = label_width - visible_len(label)
                formatted.append(f"  {label}{' ' * pad}   {value}")

        header_text = str(render_color_text(header)) if header else ""
        footer_text = str(render_color_text(footer)) if footer else ""

        content_width = max(
            (visible_len(line) for line in formatted if line),
            default=0,
        )
        inner = max(
            content_width + 2,
            visible_len(header_text) + 6,
            visible_len(footer_text) + 6,
        )

        print()
        if header_text:
            fill = inner - visible_len(header_text) - 4
            print(f"{tl}{h} {header_text} {h * fill}{h}{tr}")
        else:
            print(f"{tl}{h * inner}{tr}")

        print(f"{v}{' ' * inner}{v}")
        for line in formatted:
            if not line:
                print(f"{v}{' ' * inner}{v}")
            else:
                pad_right = inner - visible_len(line)
                print(f"{v}{line}{' ' * pad_right}{v}")
        print(f"{v}{' ' * inner}{v}")

        if footer_text:
            fill = inner - visible_len(footer_text) - 3
            print(f"{bl}{h * fill} {footer_text} {h}{br}")
        else:
            print(f"{bl}{h * inner}{br}")

    @staticmethod
    def print_help(commands: list[Command]) -> None:
        """Print a help listing; collapsed groups are flagged with a hanging ``\u25b8`` marker.

        Rows are rendered via ``print_table`` with borderless alignment; the usage
        column is dropped entirely when every row's usage is empty.
        """
        if not commands:
            return

        rows: list[list[str | ColorText]] = []
        for cmd in commands:
            if cmd.children and not cmd.expand:
                rows.append([f"\u25b8 {render_color_text(cmd.name)}", "", cmd.description])
                continue
            for name, usage, desc in ConsoleOutput._collect_help_lines([cmd], prefix=""):
                rows.append([f"  {name}", usage, desc])

        if not rows:
            return
        if not any(r[1] for r in rows):
            rows = [[r[0], r[2]] for r in rows]
        ConsoleOutput.print_table(rows)

    @staticmethod
    def _collect_help_lines(commands: list[Command], prefix: str) -> list[tuple[str, str, str]]:
        lines: list[tuple[str, str, str]] = []
        for cmd in commands:
            name = str(render_color_text(cmd.name))
            has_children = bool(cmd.children)
            desc = str(render_color_text(cmd.description))

            if has_children and not cmd.expand:
                # Collapsed group is rendered directly by print_help with its marker.
                continue

            is_group_only = cmd.handler is None and has_children
            if not is_group_only:
                lines.append((f"{prefix}{name}", cmd.usage or "", desc))
            if has_children:
                lines.extend(ConsoleOutput._collect_help_lines(cmd.children, prefix=f"{prefix}{name} "))
        return lines

    @staticmethod
    def print_json(data: object, *, indent: int = 2) -> None:
        """Pretty-print a JSON-serializable value with ANSI syntax highlighting.

        :param data: JSON-serializable value to render.
        :param indent: Number of spaces per nesting level.
        """
        print(_format_json(data, indent=indent))

    @staticmethod
    def print_line(width: int = 40) -> None:
        """Print a horizontal separator line made of ``width`` box-drawing dashes."""
        print("\u2500" * width)

    @staticmethod
    def _print_table_plain(
        rows: list[list[str]],
        col_widths: list[int],
        header_text: str,
        footer_text: str,
    ) -> None:
        if header_text:
            print(header_text)
        for row in rows:
            line = ""
            for i, cell in enumerate(row):
                pad = col_widths[i] - visible_len(cell) + 2
                line += f"{cell}{' ' * pad}"
            print(line)
        if footer_text:
            print(footer_text)

    @staticmethod
    def _print_table_boxed(
        rows: list[list[str]],
        col_widths: list[int],
        style: BoxStyle,
        header_text: str,
        footer_text: str,
    ) -> None:
        tl, tr, bl, br, h, v, lt, cross, rt = box_chars(style.name)
        inner_widths = [w + 2 for w in col_widths]

        top_line = h.join(h * w for w in inner_widths)

        if header_text:
            fill = len(top_line) - visible_len(header_text) - 3
            print(f"{tl}{h} {header_text} {h * fill}{tr}")
        else:
            print(f"{tl}{top_line}{tr}")

        for row_idx, row in enumerate(rows):
            line = v
            for i, cell in enumerate(row):
                pad = inner_widths[i] - visible_len(cell) - 1
                line += f" {cell}{' ' * pad}{v}"
            print(line)
            if row_idx == 0 and len(rows) > 1:
                print(f"{lt}{cross.join(h * w for w in inner_widths)}{rt}")

        if footer_text:
            fill = len(top_line) - visible_len(footer_text) - 3
            print(f"{bl}{h * fill} {footer_text} {h}{br}")
        else:
            print(f"{bl}{top_line}{br}")


def _format_json(value: object, *, indent: int = 2, depth: int = 0) -> str:
    """Recursively format a value as indented JSON with ANSI coloring per token type.

    :param depth: Current recursion depth used to compute leading indentation.
    """
    pad = " " * (depth * indent)
    child_pad = " " * ((depth + 1) * indent)

    if isinstance(value, dict):
        if not value:
            return "{}"
        items = [
            f"{child_pad}{colorize_text(json.dumps(k), Color.CYAN)}: {_format_json(v, indent=indent, depth=depth + 1)}"
            for k, v in value.items()
        ]
        return "{\n" + ",\n".join(items) + "\n" + pad + "}"

    if isinstance(value, list):
        if not value:
            return "[]"
        items = [child_pad + _format_json(v, indent=indent, depth=depth + 1) for v in value]
        return "[\n" + ",\n".join(items) + "\n" + pad + "]"

    return _colorize_scalar(value)


def _colorize_scalar(value: object) -> str:
    """Render a JSON scalar with a color chosen by type: null/red, bool/magenta, number/yellow, string/green."""
    if value is None:
        return colorize_text("null", Color.RED)
    if isinstance(value, bool):
        return colorize_text("true" if value else "false", Color.MAGENTA)
    if isinstance(value, (int, float)):
        return colorize_text(json.dumps(value), Color.YELLOW)
    if isinstance(value, str):
        return colorize_text(json.dumps(value), Color.GREEN)
    return json.dumps(value, default=str)

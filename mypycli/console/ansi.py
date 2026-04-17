from __future__ import annotations

import re

from mypycli.types import Color, ColorText  # noqa: TC001

_ANSI_RE = re.compile(r"\033\[[0-9;]*m")

_RESET = "\033[0m"

_COLOR_CODES: dict[str, str] = {
    "BLACK": "\033[30m",
    "RED": "\033[31m",
    "GREEN": "\033[32m",
    "YELLOW": "\033[33m",
    "BLUE": "\033[34m",
    "MAGENTA": "\033[35m",
    "CYAN": "\033[36m",
    "WHITE": "\033[37m",
    "GRAY": "\033[90m",
    "BRIGHT_RED": "\033[91m",
    "BRIGHT_GREEN": "\033[92m",
    "BRIGHT_YELLOW": "\033[93m",
    "BRIGHT_BLUE": "\033[94m",
    "BRIGHT_MAGENTA": "\033[95m",
    "BRIGHT_CYAN": "\033[96m",
    "BRIGHT_WHITE": "\033[97m",
}

_BOX_CHARS: dict[str, tuple[str, str, str, str, str, str, str, str, str]] = {
    "ROUNDED": ("╭", "╮", "╰", "╯", "─", "│", "├", "┼", "┤"),
    "SHARP": ("┌", "┐", "└", "┘", "─", "│", "├", "┼", "┤"),
    "DOUBLE": ("╔", "╗", "╚", "╝", "═", "║", "╠", "╬", "╣"),
    "ASCII": ("+", "+", "+", "+", "-", "|", "+", "+", "+"),
}


def visible_len(text: str) -> int:
    """Return visible character count, excluding ANSI escape sequences.

    :param text: String whose visible length is measured.
    """
    return len(_ANSI_RE.sub("", text))


def strip_ansi(text: str) -> str:
    """Return text with all ANSI escape sequences removed.

    :param text: String from which ANSI escape sequences are stripped.
    """
    return _ANSI_RE.sub("", text)


def colorize_text(text: str, color: Color) -> str:
    """Wrap text in ANSI color codes for the given color.

    :param text: String to wrap in color codes.
    :param color: Target color selected from the ``Color`` enum.
    :returns: Original text unchanged if the color has no known ANSI code.
    """
    code = _COLOR_CODES.get(color.name, "")
    if not code:
        return text
    return f"{code}{text}{_RESET}"


def render_color_text(ct: str | ColorText) -> str:
    """Render a plain string or ColorText as an ANSI-colored string.

    :param ct: Source string or ``ColorText`` to render.
    """
    if isinstance(ct, str):
        return ct
    return colorize_text(ct.text, ct.color)


def box_chars(style_name: str) -> tuple[str, str, str, str, str, str, str, str, str]:
    """Return box-drawing characters for a style as ``(tl, tr, bl, br, h, v, lt, cross, rt)``.

    :param style_name: One of ``ROUNDED``, ``SHARP``, ``DOUBLE``, ``ASCII``; unknown falls back to ``ROUNDED``.
    """
    return _BOX_CHARS.get(style_name, _BOX_CHARS["ROUNDED"])

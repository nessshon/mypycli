from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable


class Color(Enum):
    """Named ANSI colors for terminal output."""

    BLACK = "black"
    RED = "red"
    GREEN = "green"
    YELLOW = "yellow"
    BLUE = "blue"
    MAGENTA = "magenta"
    CYAN = "cyan"
    WHITE = "white"
    GRAY = "gray"
    BRIGHT_RED = "bright_red"
    BRIGHT_GREEN = "bright_green"
    BRIGHT_YELLOW = "bright_yellow"
    BRIGHT_BLUE = "bright_blue"
    BRIGHT_MAGENTA = "bright_magenta"
    BRIGHT_CYAN = "bright_cyan"
    BRIGHT_WHITE = "bright_white"


class BoxStyle(Enum):
    """Box-drawing styles for panels and tables."""

    ROUNDED = "rounded"
    SHARP = "sharp"
    DOUBLE = "double"
    ASCII = "ascii"


@dataclass(frozen=True)
class ColorText:
    """Text bound to a color for terminal rendering.

    :param text: Raw text content.
    :param color: Color applied when rendered.
    """

    text: str
    color: Color

    def __str__(self) -> str:
        return self.text


@dataclass
class Command:
    """Console command descriptor with optional nested subcommands.

    :param name: Command name, plain or styled.
    :param handler: Callable invoked on dispatch, or ``None`` for group-only commands.
    :param description: Short help text shown in listings.
    :param usage: Argument hint displayed in help.
    :param children: Subcommands for hierarchical dispatch.
    :param expand: When ``True``, subcommands are listed inline in the main help.
        When ``False`` (default), the group is shown as a single line and its
        subcommands are visible only after the user invokes it or runs ``help <group>``.
    """

    name: str | ColorText
    handler: Callable[..., Any] | None = None
    description: str | ColorText = ""
    usage: str = ""
    children: list[Command] = field(default_factory=list)
    expand: bool = False

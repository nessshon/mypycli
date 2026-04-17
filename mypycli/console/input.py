from __future__ import annotations

import getpass
import sys
import termios
import tty
from typing import TYPE_CHECKING

from mypycli.console.ansi import colorize_text, render_color_text
from mypycli.i18n.internal import _
from mypycli.types import Color, ColorText
from mypycli.utils.system import is_tty

if TYPE_CHECKING:
    from collections.abc import Callable

_ARROW_UP = "\x1b[A"
_ARROW_DOWN = "\x1b[B"
_ARROW_RIGHT = "\x1b[C"
_ARROW_LEFT = "\x1b[D"
_HOME_KEYS = ("\x1b[H", "\x1b[1~", "\x01")
_END_KEYS = ("\x1b[F", "\x1b[4~", "\x05")
_BACKSPACE_KEYS = ("\x7f", "\b", "\x08")
_DELETE_KEY = "\x1b[3~"
_CTRL_U = "\x15"
_CTRL_W = "\x17"
_ENTER = ("\r", "\n")
_CTRL_C = "\x03"

_POINTER = "\u276f"
_RADIO_ON = "\u25c9"
_RADIO_OFF = "\u25cb"


def _read_key() -> str:
    """Read one keypress from stdin in raw mode; returns the full escape sequence for special keys.

    :raises EOFError: When stdin reaches end-of-file (e.g. Ctrl+D on an empty line).
    """
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if not ch:
            raise EOFError
        if ch != "\x1b":
            return ch
        nxt = sys.stdin.read(1)
        if not nxt:
            raise EOFError
        if nxt != "[":
            return ch + nxt
        seq = ch + nxt
        while True:
            c = sys.stdin.read(1)
            if not c:
                raise EOFError
            seq += c
            if c.isalpha() or c == "~":
                return seq
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _clear_lines(count: int) -> None:
    """Move the cursor up and erase ``count`` lines above the current position.

    :param count: Number of lines above the cursor to erase.
    """
    for _i in range(count):
        sys.stdout.write("\x1b[A\x1b[2K")
    sys.stdout.flush()


def _text(value: str | ColorText) -> str:
    """Return the underlying plain text of a string or ColorText, stripping color metadata.

    :param value: Source string or ``ColorText`` to extract plain text from.
    """
    return value.text if isinstance(value, ColorText) else value


def _edit_line(prompt_str: str, initial: str) -> str:
    """Run an inline line editor pre-filled with ``initial`` and return the final buffer on Enter.

    :param prompt_str: Rendered prompt text printed before the editable buffer.
    :param initial: Initial buffer content; placed at the cursor position.
    :raises KeyboardInterrupt: When the user presses Ctrl+C.
    """
    buffer = list(initial)
    cursor = len(buffer)

    def _redraw() -> None:
        sys.stdout.write(f"\r{prompt_str}{''.join(buffer)}\x1b[K")
        back = len(buffer) - cursor
        if back:
            sys.stdout.write(f"\x1b[{back}D")
        sys.stdout.flush()

    _redraw()
    while True:
        key = _read_key()
        if key in _ENTER:
            sys.stdout.write("\r\n")
            sys.stdout.flush()
            return "".join(buffer)
        if key == _CTRL_C:
            sys.stdout.write("\r\n")
            sys.stdout.flush()
            raise KeyboardInterrupt
        if key in _BACKSPACE_KEYS:
            if cursor > 0:
                del buffer[cursor - 1]
                cursor -= 1
        elif key == _DELETE_KEY:
            if cursor < len(buffer):
                del buffer[cursor]
        elif key == _ARROW_LEFT:
            cursor = max(0, cursor - 1)
        elif key == _ARROW_RIGHT:
            cursor = min(len(buffer), cursor + 1)
        elif key in _HOME_KEYS:
            cursor = 0
        elif key in _END_KEYS:
            cursor = len(buffer)
        elif key == _CTRL_U:
            del buffer[:cursor]
            cursor = 0
        elif key == _CTRL_W:
            while cursor > 0 and buffer[cursor - 1] == " ":
                del buffer[cursor - 1]
                cursor -= 1
            while cursor > 0 and buffer[cursor - 1] != " ":
                del buffer[cursor - 1]
                cursor -= 1
        elif len(key) == 1 and key.isprintable():
            buffer.insert(cursor, key)
            cursor += 1
        _redraw()


def _print_invalid(err: str) -> None:
    """Print the translated invalid-input message in red for interactive retry feedback."""
    print(colorize_text(_("console.invalid_input", error=err), Color.RED))


class ConsoleInput:
    """Mixin providing interactive terminal prompt methods (text, secret, confirm, select, multiselect)."""

    @staticmethod
    def input(
        prompt: str | ColorText,
        *,
        default: str | ColorText | None = None,
        validate: Callable[[str], str | None] | None = None,
    ) -> str:
        """Prompt the user for a line of text.

        TTY: pre-fills the buffer with ``default`` for in-place editing; the returned
        value equals the buffer at Enter time, so clearing it returns ``""``. Non-TTY:
        reads a line via ``input()`` and falls back to ``default`` on empty input.

        When ``validate`` is provided it is called with the submitted string and must
        return ``None`` to accept it or an error message to reject it. On a TTY the
        prompt is redrawn with the rejected value kept in the buffer for editing; on
        non-TTY a ``ValueError`` is raised.

        :param prompt: Prompt label shown before the input field.
        :param default: Initial buffer (TTY) or fallback on empty input (non-TTY); ``None`` means no default.
        :param validate: Callable returning ``None`` on success or an error message to reject the input.
        :raises KeyboardInterrupt: When the user presses Ctrl+C in the TTY editor.
        :raises ValueError: Non-TTY input fails ``validate``.
        """
        rendered = render_color_text(prompt)
        default_text = _text(default) if default is not None else ""
        if not is_tty():
            line = input(f"{rendered}: ")
            val = line or default_text
            if validate is not None:
                err = validate(val)
                if err is not None:
                    raise ValueError(f"Invalid input for {rendered!r}: {err}")
            return val
        buffer = default_text
        while True:
            val = _edit_line(f"{rendered}: ", buffer)
            if validate is None:
                return val
            err = validate(val)
            if err is None:
                return val
            _print_invalid(err)
            buffer = val

    @staticmethod
    def secret(
        prompt: str | ColorText,
        *,
        validate: Callable[[str], str | None] | None = None,
    ) -> str:
        """Prompt the user for a line of text with terminal echo disabled.

        When ``validate`` is provided it is called with the entered string; on a TTY
        the prompt repeats until the value is accepted, on non-TTY a ``ValueError``
        is raised. ``secret`` never echoes the rejected value, so retries start fresh.

        :param prompt: Prompt label shown before the hidden input field.
        :param validate: Callable returning ``None`` on success or an error message to reject the input.
        :raises ValueError: Non-TTY input fails ``validate``.
        """
        rendered = render_color_text(prompt)
        if not is_tty():
            val = getpass.getpass(f"{rendered}: ")
            if validate is not None:
                err = validate(val)
                if err is not None:
                    raise ValueError(f"Invalid input for {rendered!r}: {err}")
            return val
        while True:
            val = getpass.getpass(f"{rendered}: ")
            if validate is None:
                return val
            err = validate(val)
            if err is None:
                return val
            _print_invalid(err)

    @staticmethod
    def confirm(prompt: str | ColorText, *, default: bool = False) -> bool:
        """Ask a yes/no question.

        :param prompt: Question label shown before the ``[Y/n]`` / ``[y/N]`` hint.
        :param default: Value returned on empty input; also controls which side is shown capitalized
            in ``[Y/n]`` / ``[y/N]``.
        """
        hint = "[Y/n]" if default else "[y/N]"
        result = input(f"{render_color_text(prompt)} {hint}: ").strip().lower()
        if not result:
            return default
        return result in ("y", "yes")

    @staticmethod
    def select(prompt: str | ColorText, choices: list[str | ColorText]) -> str:
        """Present a single-choice menu navigated by arrow keys and confirmed with Enter.

        :param prompt: Prompt label shown above the menu.
        :param choices: Available menu entries rendered one per line.
        :returns: Plain text of the chosen item.
        :raises KeyboardInterrupt: When the user presses Ctrl+C.
        """
        cursor = 0
        pointer = colorize_text(_POINTER, Color.GREEN)
        labels = [render_color_text(c) for c in choices]
        values = [_text(c) for c in choices]

        def _render() -> None:
            for i in range(len(choices)):
                line = f"  {pointer} {colorize_text(values[i], Color.CYAN)}" if i == cursor else f"    {labels[i]}"
                sys.stdout.write(line + "\n")
            sys.stdout.flush()

        print(render_color_text(prompt))
        _render()

        while True:
            key = _read_key()
            if key == _ARROW_UP and cursor > 0:
                cursor -= 1
            elif key == _ARROW_DOWN and cursor < len(choices) - 1:
                cursor += 1
            elif key in _ENTER:
                _clear_lines(len(choices))
                print(f"  {pointer} {values[cursor]}")
                return values[cursor]
            elif key == _CTRL_C:
                _clear_lines(len(choices))
                raise KeyboardInterrupt

            _clear_lines(len(choices))
            _render()

    @staticmethod
    def multiselect(prompt: str | ColorText, choices: list[str | ColorText]) -> list[str]:
        """Present a multi-choice menu: arrow keys navigate, space toggles, Enter confirms.

        :param prompt: Prompt label shown above the menu.
        :param choices: Available menu entries rendered one per line.
        :returns: Plain text of the selected items in original order; empty list if none selected.
        :raises KeyboardInterrupt: When the user presses Ctrl+C.
        """
        cursor = 0
        selected: set[int] = set()
        pointer = colorize_text(_POINTER, Color.GREEN)
        labels = [render_color_text(c) for c in choices]
        values = [_text(c) for c in choices]

        def _render() -> None:
            for i in range(len(choices)):
                marker = colorize_text(_RADIO_ON, Color.GREEN) if i in selected else _RADIO_OFF
                line = (
                    f"  {pointer} {marker} {colorize_text(values[i], Color.CYAN)}"
                    if i == cursor
                    else f"    {marker} {labels[i]}"
                )
                sys.stdout.write(line + "\n")
            sys.stdout.flush()

        print(render_color_text(prompt))
        _render()

        while True:
            key = _read_key()
            if key == _ARROW_UP and cursor > 0:
                cursor -= 1
            elif key == _ARROW_DOWN and cursor < len(choices) - 1:
                cursor += 1
            elif key == " ":
                if cursor in selected:
                    selected.discard(cursor)
                else:
                    selected.add(cursor)
            elif key in _ENTER:
                _clear_lines(len(choices))
                for idx in range(len(choices)):
                    if idx in selected:
                        print(f"  {colorize_text(_RADIO_ON, Color.GREEN)} {values[idx]}")
                return [values[idx] for idx in sorted(selected)]
            elif key == _CTRL_C:
                _clear_lines(len(choices))
                raise KeyboardInterrupt

            _clear_lines(len(choices))
            _render()

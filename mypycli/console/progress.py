from __future__ import annotations

from typing import TYPE_CHECKING

from mypycli.console.ansi import colorize_text
from mypycli.types import Color

if TYPE_CHECKING:
    from types import TracebackType
    from typing import IO


class ProgressLine:
    r"""Single-line progress indicator that rewrites the current terminal line.

    TTY: ``update`` rewrites the line via ``\r`` + clear-EOL; ``finish``/``fail``
    emit the last line and terminate with ``\n``. Non-TTY: each call prints a
    standalone line. Cursor is hidden and restored around the block in TTY mode.

    With ``total`` set, ``update`` auto-prepends ``[n/total]`` (gray in TTY,
    plain in non-TTY); ``finish``/``fail`` carry no counter.

    :param stream: Output stream to write to (typically ``sys.stdout``).
    :param tty: Whether ``stream`` is an interactive terminal.
    :param total: Step count for the ``[n/total]`` prefix; ``None`` disables it.
    """

    def __init__(self, stream: IO[str], *, tty: bool, total: int | None = None) -> None:
        self._stream = stream
        self._tty = tty
        self._total = total
        self._n = 0

    def __enter__(self) -> ProgressLine:
        if self._tty:
            self._stream.write("\x1b[?25l")
            self._stream.flush()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._tty:
            self._stream.write("\x1b[?25h")
            self._stream.flush()

    def update(self, text: str, *, color: Color | None = None) -> None:
        """Replace the live line (TTY) or print a standalone line (non-TTY).

        With ``total`` set on the constructor, prepends ``[n/total]`` to the body.
        """
        body = colorize_text(text, color) if color is not None else text
        if self._total is not None:
            self._n += 1
            tag = f"[{self._n}/{self._total}]"
            prefix = colorize_text(tag, Color.GRAY) if self._tty else tag
            rendered = f"{prefix} {body}"
        else:
            rendered = body
        if self._tty:
            self._stream.write(f"\r\x1b[2K{rendered}")
        else:
            self._stream.write(f"{rendered}\n")
        self._stream.flush()

    def finish(self, text: str, *, color: Color | None = None) -> None:
        """Emit the final success line and terminate the active span."""
        self._emit_final(text, color)

    def fail(self, text: str, *, color: Color | None = None) -> None:
        """Emit the final failure line and terminate the active span."""
        self._emit_final(text, color)

    def _emit_final(self, text: str, color: Color | None) -> None:
        rendered = colorize_text(text, color) if color is not None else text
        if self._tty:
            self._stream.write(f"\r\x1b[2K{rendered}\n")
        else:
            self._stream.write(f"{rendered}\n")
        self._stream.flush()

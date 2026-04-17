from __future__ import annotations

import io
from unittest.mock import MagicMock

import pytest

from mypycli.console.console import Console
from mypycli.console.progress import ProgressLine
from mypycli.types import Color


class TestProgressLineTTY:
    def test_update_writes_cr_and_clear(self) -> None:
        buf = io.StringIO()
        with ProgressLine(buf, tty=True) as line:
            line.update("step 1")
        out = buf.getvalue()
        assert "\r\x1b[2K" in out
        assert "step 1" in out

    def test_finish_terminates_with_newline(self) -> None:
        buf = io.StringIO()
        with ProgressLine(buf, tty=True) as line:
            line.finish("done")
        assert "\r\x1b[2Kdone\n" in buf.getvalue()

    def test_fail_terminates_with_newline(self) -> None:
        buf = io.StringIO()
        with ProgressLine(buf, tty=True) as line:
            line.fail("oops")
        assert "\r\x1b[2Koops\n" in buf.getvalue()

    def test_hides_and_restores_cursor(self) -> None:
        buf = io.StringIO()
        with ProgressLine(buf, tty=True):
            pass
        raw = buf.getvalue()
        assert "\x1b[?25l" in raw
        assert raw.endswith("\x1b[?25h")

    def test_restores_cursor_on_exception(self) -> None:
        buf = io.StringIO()
        try:
            with ProgressLine(buf, tty=True):
                raise ValueError("boom")
        except ValueError:
            pass
        assert buf.getvalue().endswith("\x1b[?25h")

    def test_update_applies_color(self) -> None:
        buf = io.StringIO()
        with ProgressLine(buf, tty=True) as line:
            line.update("step", color=Color.GREEN)
        assert "\x1b[32m" in buf.getvalue()


class TestProgressLineNonTTY:
    def test_update_prints_standalone_lines(self) -> None:
        buf = io.StringIO()
        with ProgressLine(buf, tty=False) as line:
            line.update("step 1")
            line.update("step 2")
        out = buf.getvalue()
        assert "step 1\n" in out
        assert "step 2\n" in out
        assert "\r" not in out

    def test_finish_prints_plain_line(self) -> None:
        buf = io.StringIO()
        with ProgressLine(buf, tty=False) as line:
            line.finish("done")
        assert buf.getvalue() == "done\n"

    def test_cursor_codes_not_emitted(self) -> None:
        buf = io.StringIO()
        with ProgressLine(buf, tty=False) as line:
            line.update("x")
            line.finish("y")
        raw = buf.getvalue()
        assert "\x1b[?25l" not in raw
        assert "\x1b[?25h" not in raw


class TestProgressLineCounterTTY:
    def test_prefix_increments_on_each_update(self) -> None:
        buf = io.StringIO()
        with ProgressLine(buf, tty=True, total=7) as line:
            line.update("one")
            line.update("two")
            line.update("three")
        out = buf.getvalue()
        assert "\x1b[90m[1/7]\x1b[0m one" in out
        assert "\x1b[90m[2/7]\x1b[0m two" in out
        assert "\x1b[90m[3/7]\x1b[0m three" in out

    def test_prefix_does_not_wrap_body_color(self) -> None:
        buf = io.StringIO()
        with ProgressLine(buf, tty=True, total=3) as line:
            line.update("step", color=Color.CYAN)
        out = buf.getvalue()
        assert "\x1b[90m[1/3]\x1b[0m \x1b[36mstep\x1b[0m" in out

    def test_over_total_keeps_incrementing(self) -> None:
        buf = io.StringIO()
        with ProgressLine(buf, tty=True, total=2) as line:
            line.update("a")
            line.update("b")
            line.update("c")
        assert "\x1b[90m[3/2]\x1b[0m c" in buf.getvalue()

    def test_finish_has_no_prefix(self) -> None:
        buf = io.StringIO()
        with ProgressLine(buf, tty=True, total=3) as line:
            line.update("step")
            line.finish("done")
        # `finish` emits a bare `\r\x1b[2Kdone\n` — no counter tag between the
        # clear-EOL and the body.
        assert "\r\x1b[2Kdone\n" in buf.getvalue()

    def test_fail_has_no_prefix(self) -> None:
        buf = io.StringIO()
        with ProgressLine(buf, tty=True, total=3) as line:
            line.update("step")
            line.fail("oops")
        assert "\r\x1b[2Koops\n" in buf.getvalue()


class TestProgressLineCounterNonTTY:
    def test_plain_prefix_no_ansi(self) -> None:
        buf = io.StringIO()
        with ProgressLine(buf, tty=False, total=7) as line:
            line.update("one")
            line.update("two")
        out = buf.getvalue()
        assert "[1/7] one\n" in out
        assert "[2/7] two\n" in out
        assert "\x1b[90m" not in out

    def test_finish_has_no_prefix_non_tty(self) -> None:
        buf = io.StringIO()
        with ProgressLine(buf, tty=False, total=3) as line:
            line.update("step")
            line.finish("done")
        lines = buf.getvalue().splitlines()
        assert lines[-1] == "done"


class TestProgressLineNoCounterByDefault:
    def test_no_prefix_when_total_none_tty(self) -> None:
        buf = io.StringIO()
        with ProgressLine(buf, tty=True) as line:
            line.update("one")
        assert "[1/" not in buf.getvalue()

    def test_no_prefix_when_total_none_non_tty(self) -> None:
        buf = io.StringIO()
        with ProgressLine(buf, tty=False) as line:
            line.update("one")
        assert "[" not in buf.getvalue()


class TestPrintProgressValidation:
    def test_total_zero_rejected(self) -> None:
        c = Console(app=MagicMock())
        with pytest.raises(ValueError, match="positive integer"):
            c.print_progress(total=0)

    def test_total_negative_rejected(self) -> None:
        c = Console(app=MagicMock())
        with pytest.raises(ValueError, match="positive integer"):
            c.print_progress(total=-1)

    def test_total_none_is_accepted(self) -> None:
        c = Console(app=MagicMock())
        line = c.print_progress()
        assert isinstance(line, ProgressLine)

    def test_total_positive_is_accepted(self) -> None:
        c = Console(app=MagicMock())
        line = c.print_progress(total=3)
        assert isinstance(line, ProgressLine)

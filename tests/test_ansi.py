from __future__ import annotations

from mypycli.console.ansi import box_chars, colorize_text, render_color_text, strip_ansi, visible_len
from mypycli.types import Color, ColorText


class TestVisibleLen:
    def test_plain_text(self) -> None:
        assert visible_len("hello") == 5

    def test_ignores_ansi_codes(self) -> None:
        assert visible_len("\033[31mhello\033[0m") == 5

    def test_mixed(self) -> None:
        assert visible_len(f"a {colorize_text('b', Color.RED)} c") == 5


class TestStripAnsi:
    def test_removes_codes(self) -> None:
        assert strip_ansi("\033[1;36mhi\033[0m") == "hi"

    def test_plain_unchanged(self) -> None:
        assert strip_ansi("plain") == "plain"


class TestColorize:
    def test_wraps_known_color(self) -> None:
        result = colorize_text("x", Color.RED)
        assert result.startswith("\033[31m")
        assert result.endswith("\033[0m")
        assert "x" in result

    def test_render_color_text_passthrough_for_str(self) -> None:
        assert render_color_text("plain") == "plain"

    def test_render_color_text_applies_color(self) -> None:
        rendered = render_color_text(ColorText("x", Color.GREEN))
        assert "x" in rendered
        assert "\033[32m" in rendered


class TestBoxChars:
    def test_known_style(self) -> None:
        chars = box_chars("ROUNDED")
        assert chars[0] == "╭"
        assert chars[4] == "─"

    def test_unknown_falls_back_to_rounded(self) -> None:
        assert box_chars("UNKNOWN") == box_chars("ROUNDED")

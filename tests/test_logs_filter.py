from __future__ import annotations

from mypycli.cli.commands.logs import _filter_log_stream, _line_passes, _match_module

_INFO_LINE = "[INFO    ] 2026-04-16 12:00:00 <main> demo.system: started\n"
_DEBUG_LINE = "[DEBUG   ] 2026-04-16 12:00:01 <main> demo.worker: tick\n"
_ERROR_APP_LINE = "[ERROR   ] 2026-04-16 12:00:02 <main> demo: failure\n"
_CONT_LINE = "  traceback continuation line\n"


class TestMatchModule:
    def test_exact_match(self) -> None:
        assert _match_module("demo", "demo") is True

    def test_suffix_match(self) -> None:
        assert _match_module("demo.worker", "worker") is True

    def test_partial_suffix_does_not_match(self) -> None:
        assert _match_module("demo.worker2", "worker") is False


class TestLinePasses:
    def test_level_threshold(self) -> None:
        assert _line_passes(_DEBUG_LINE, 20, None, True) is False
        assert _line_passes(_INFO_LINE, 20, None, True) is True

    def test_module_filter_matches_suffix(self) -> None:
        assert _line_passes(_INFO_LINE, None, "system", True) is True
        assert _line_passes(_INFO_LINE, None, "worker", True) is False

    def test_continuation_inherits_previous_keep(self) -> None:
        assert _line_passes(_CONT_LINE, None, None, True) is True
        assert _line_passes(_CONT_LINE, None, None, False) is False


class TestFilterLogStream:
    def test_drops_line_and_its_continuation(self) -> None:
        lines = [_DEBUG_LINE, _CONT_LINE, _INFO_LINE]
        result = list(_filter_log_stream(lines, 20, None))
        assert result == [_INFO_LINE]

    def test_keeps_line_and_its_continuation(self) -> None:
        lines = [_ERROR_APP_LINE, _CONT_LINE, _INFO_LINE]
        result = list(_filter_log_stream(lines, 40, None))
        assert result == [_ERROR_APP_LINE, _CONT_LINE]

    def test_module_filter_is_applied(self) -> None:
        lines = [_INFO_LINE, _DEBUG_LINE]
        result = list(_filter_log_stream(lines, None, "system"))
        assert result == [_INFO_LINE]

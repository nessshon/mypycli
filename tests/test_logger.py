from __future__ import annotations

import logging

import pytest

from mypycli.logger import PlainFormatter


@pytest.fixture
def record_with_exc() -> logging.LogRecord:
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        import sys

        return logging.LogRecord(
            name="demo",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="something failed",
            args=None,
            exc_info=sys.exc_info(),
        )


class TestPlainFormatter:
    def test_includes_message(self) -> None:
        record = logging.LogRecord("demo", logging.INFO, __file__, 1, "hi", None, None)
        output = PlainFormatter().format(record)
        assert "hi" in output
        assert "demo" in output
        assert "INFO" in output

    def test_appends_traceback(self, record_with_exc: logging.LogRecord) -> None:
        output = PlainFormatter().format(record_with_exc)
        assert "something failed" in output
        assert "Traceback" in output
        assert "RuntimeError: boom" in output

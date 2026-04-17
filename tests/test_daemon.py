from __future__ import annotations

import os
from typing import TYPE_CHECKING

from mypycli.utils.daemon import is_alive, read_pid

if TYPE_CHECKING:
    from pathlib import Path


class TestReadPid:
    def test_reads_valid_pid(self, tmp_path: Path) -> None:
        p = tmp_path / "app.pid"
        p.write_text("1234\n")
        assert read_pid(p) == 1234

    def test_missing_returns_none(self, tmp_path: Path) -> None:
        assert read_pid(tmp_path / "missing.pid") is None

    def test_non_integer_returns_none(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.pid"
        p.write_text("not-a-number")
        assert read_pid(p) is None


class TestIsAlive:
    def test_current_process_alive(self) -> None:
        assert is_alive(os.getpid()) is True

    def test_unused_pid_returns_false(self) -> None:
        assert is_alive(2**30) is False

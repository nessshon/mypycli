from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import pytest

from mypycli.utils import system
from mypycli.utils.system import is_tty, run, run_as_root

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


class TestIsTty:
    @pytest.mark.parametrize(
        ("stdin", "stdout", "expected"),
        [
            (True, True, True),
            (False, True, False),
            (True, False, False),
            (False, False, False),
        ],
    )
    def test_requires_both_streams(
        self, monkeypatch: MonkeyPatch, stdin: bool, stdout: bool, expected: bool
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: stdin)
        monkeypatch.setattr("sys.stdout.isatty", lambda: stdout)
        assert is_tty() is expected


class TestRunCheck:
    def test_zero_exit_no_raise_without_check(self) -> None:
        result = run(["true"])
        assert result.returncode == 0

    def test_nonzero_exit_no_raise_by_default(self) -> None:
        result = run(["false"])
        assert result.returncode != 0

    def test_zero_exit_with_check_returns(self) -> None:
        result = run(["true"], check=True)
        assert result.returncode == 0

    def test_nonzero_exit_with_check_raises(self) -> None:
        with pytest.raises(subprocess.CalledProcessError) as exc:
            run(["false"], check=True)
        assert exc.value.returncode != 0
        assert exc.value.cmd == ["false"]


class TestRunAsRootCheck:
    def test_cmd_in_error_is_unwrapped_original(self, monkeypatch: MonkeyPatch) -> None:
        """CalledProcessError.cmd holds the user-given args, not any sudo/su wrapping."""
        monkeypatch.setattr(system, "is_root", lambda: True)
        with pytest.raises(subprocess.CalledProcessError) as exc:
            run_as_root(["false"], check=True)
        assert exc.value.cmd == ["false"]
        assert "sudo" not in exc.value.cmd
        assert "su" not in exc.value.cmd

    def test_zero_exit_with_check_returns(self, monkeypatch: MonkeyPatch) -> None:
        monkeypatch.setattr(system, "is_root", lambda: True)
        result = run_as_root(["true"], check=True)
        assert result.returncode == 0

    def test_nonzero_no_raise_by_default(self, monkeypatch: MonkeyPatch) -> None:
        monkeypatch.setattr(system, "is_root", lambda: True)
        result = run_as_root(["false"])
        assert result.returncode != 0

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from mypycli.console.input import ConsoleInput

if TYPE_CHECKING:
    from _pytest.capture import CaptureFixture
    from _pytest.monkeypatch import MonkeyPatch


def positive_int(raw: str) -> str | None:
    """Sample validator: accept strings parseable as positive integers."""
    try:
        if int(raw) <= 0:
            return "must be positive"
    except ValueError:
        return "must be an integer"
    return None


def _force_non_tty(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    monkeypatch.setattr("sys.stdout.isatty", lambda: False)


def _force_tty(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)


class TestInputNonTTY:
    def test_valid_returns(self, monkeypatch: MonkeyPatch) -> None:
        _force_non_tty(monkeypatch)
        monkeypatch.setattr("builtins.input", lambda _: "7")
        assert ConsoleInput.input("n", validate=positive_int) == "7"

    def test_invalid_raises(self, monkeypatch: MonkeyPatch) -> None:
        _force_non_tty(monkeypatch)
        monkeypatch.setattr("builtins.input", lambda _: "abc")
        with pytest.raises(ValueError, match="must be an integer"):
            ConsoleInput.input("n", validate=positive_int)

    def test_empty_falls_back_to_default_then_validates(self, monkeypatch: MonkeyPatch) -> None:
        _force_non_tty(monkeypatch)
        monkeypatch.setattr("builtins.input", lambda _: "")
        assert ConsoleInput.input("n", default="3", validate=positive_int) == "3"

    def test_empty_default_fails_validation(self, monkeypatch: MonkeyPatch) -> None:
        _force_non_tty(monkeypatch)
        monkeypatch.setattr("builtins.input", lambda _: "")
        with pytest.raises(ValueError, match="must be an integer"):
            ConsoleInput.input("n", validate=positive_int)

    def test_no_validator_returns(self, monkeypatch: MonkeyPatch) -> None:
        _force_non_tty(monkeypatch)
        monkeypatch.setattr("builtins.input", lambda _: "anything")
        assert ConsoleInput.input("n") == "anything"


class TestInputTTY:
    def test_retries_until_valid(self, monkeypatch: MonkeyPatch, capsys: CaptureFixture[str]) -> None:
        _force_tty(monkeypatch)
        answers = iter(["-1", "abc", "5"])
        seen_buffers: list[str] = []

        def fake_edit_line(_prompt: str, buffer: str) -> str:
            seen_buffers.append(buffer)
            return next(answers)

        monkeypatch.setattr("mypycli.console.input._edit_line", fake_edit_line)

        assert ConsoleInput.input("n", validate=positive_int) == "5"
        out = capsys.readouterr().out
        assert out.count("Invalid: must be positive") == 1
        assert out.count("Invalid: must be an integer") == 1
        assert seen_buffers == ["", "-1", "abc"]

    def test_valid_first_try_no_print(self, monkeypatch: MonkeyPatch, capsys: CaptureFixture[str]) -> None:
        _force_tty(monkeypatch)
        monkeypatch.setattr("mypycli.console.input._edit_line", lambda _p, _b: "1")
        assert ConsoleInput.input("n", validate=positive_int) == "1"
        assert "Invalid" not in capsys.readouterr().out

    def test_no_validator_single_shot(self, monkeypatch: MonkeyPatch) -> None:
        _force_tty(monkeypatch)
        monkeypatch.setattr("mypycli.console.input._edit_line", lambda _p, _b: "raw")
        assert ConsoleInput.input("n") == "raw"


class TestSecretNonTTY:
    def test_valid_returns(self, monkeypatch: MonkeyPatch) -> None:
        _force_non_tty(monkeypatch)
        monkeypatch.setattr("mypycli.console.input.getpass.getpass", lambda _: "12")
        assert ConsoleInput.secret("pw", validate=positive_int) == "12"

    def test_invalid_raises(self, monkeypatch: MonkeyPatch) -> None:
        _force_non_tty(monkeypatch)
        monkeypatch.setattr("mypycli.console.input.getpass.getpass", lambda _: "0")
        with pytest.raises(ValueError, match="must be positive"):
            ConsoleInput.secret("pw", validate=positive_int)


class TestSecretTTY:
    def test_retries_until_valid(self, monkeypatch: MonkeyPatch, capsys: CaptureFixture[str]) -> None:
        _force_tty(monkeypatch)
        answers = iter(["", "abc", "9"])
        monkeypatch.setattr("mypycli.console.input.getpass.getpass", lambda _: next(answers))

        assert ConsoleInput.secret("pw", validate=positive_int) == "9"
        out = capsys.readouterr().out
        assert out.count("Invalid: must be an integer") == 2

    def test_no_validator_single_shot(self, monkeypatch: MonkeyPatch) -> None:
        _force_tty(monkeypatch)
        monkeypatch.setattr("mypycli.console.input.getpass.getpass", lambda _: "top-secret")
        assert ConsoleInput.secret("pw") == "top-secret"

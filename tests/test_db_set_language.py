from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import mypycli
from mypycli import Application
from mypycli.console.builtin import cmd_db_set
from mypycli.database import DatabaseSchema
from mypycli.i18n import Translator

if TYPE_CHECKING:
    import pytest


_LIB_LOCALES = Path(mypycli.__file__).parent / "i18n" / "locales"


def _make_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Application[Any]:
    monkeypatch.setenv("LANG", "en")
    t = Translator(_LIB_LOCALES)
    app = Application(
        db_schema=DatabaseSchema,
        work_dir=tmp_path / "wd",
        name="demo",
        translator=t,
    )
    app.start()
    return app


def test_db_set_language_valid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    app = _make_app(tmp_path, monkeypatch)
    cmd_db_set(app, ["language", "ru"])
    assert app.db.language == "ru"
    assert "Restart" in capsys.readouterr().out


def test_db_set_language_invalid_blocks_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    app = _make_app(tmp_path, monkeypatch)
    before = app.db.language
    cmd_db_set(app, ["language", "xx"])
    assert app.db.language == before
    out = capsys.readouterr().out
    assert "Unknown language" in out
    assert "xx" in out


def test_db_set_debug_prints_restart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    app = _make_app(tmp_path, monkeypatch)
    cmd_db_set(app, ["debug", "true"])
    assert "Restart" in capsys.readouterr().out


def test_db_set_other_field_no_restart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    app = _make_app(tmp_path, monkeypatch)
    cmd_db_set(app, ["unrelated_field", "value"])
    assert "Restart" not in capsys.readouterr().out

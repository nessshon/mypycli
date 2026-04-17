from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from mypycli import Application
from mypycli.database import DatabaseSchema
from mypycli.i18n import Translator
from mypycli.i18n import internal as _i18n_internal

if TYPE_CHECKING:
    from pathlib import Path


def _make_locales(tmp_path: Path, langs: tuple[str, ...] = ("en", "ru")) -> Path:
    d = tmp_path / "locales"
    d.mkdir()
    for lang in langs:
        (d / f"{lang}.yml").write_text("mypycli: {}\n", encoding="utf-8")
    return d


def _make_app(
    tmp_path: Path, translator: Translator, *, name: str = "demo"
) -> Application[DatabaseSchema]:
    return Application(
        db_schema=DatabaseSchema,
        work_dir=tmp_path / "wd",
        name=name,
        translator=translator,
    )


def test_start_uses_db_language_when_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("LANG", raising=False)
    t = Translator(_make_locales(tmp_path))
    app = _make_app(tmp_path, t)
    app.db.load(auto_create=True)
    app.db.language = "ru"
    app.start()
    assert t.language == "ru"
    assert app.db.language == "ru"


def test_start_detects_from_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LANG", "ru_RU.UTF-8")
    t = Translator(_make_locales(tmp_path))
    app = _make_app(tmp_path, t)
    app.start()
    assert t.language == "ru"
    assert app.db.language == "ru"


def test_start_fallback_to_en_when_env_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LANG", "fr_FR.UTF-8")
    t = Translator(_make_locales(tmp_path))
    app = _make_app(tmp_path, t)
    app.start()
    assert t.language == "en"
    assert app.db.language == "en"


def test_start_rerolves_when_db_language_invalid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LANG", "en")
    t = Translator(_make_locales(tmp_path))
    app = _make_app(tmp_path, t)
    app.db.load(auto_create=True)
    app.db.language = "de"
    app.start()
    assert t.language == "en"
    assert app.db.language == "en"


def test_start_raises_when_no_catalogs(tmp_path: Path) -> None:
    empty = tmp_path / "locales"
    empty.mkdir()
    t = Translator(empty)
    app = _make_app(tmp_path, t)
    with pytest.raises(RuntimeError, match="No language catalogs"):
        app.start()


def test_start_uses_first_available_when_en_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LANG", "fr")
    t = Translator(_make_locales(tmp_path, langs=("ru", "zh")))
    app = _make_app(tmp_path, t)
    app.start()
    assert t.language in {"ru", "zh"}
    assert app.db.language == t.language


def test_start_binds_internal_underscore(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LANG", "en")
    d = _make_locales(tmp_path)
    (d / "en.yml").write_text(
        'mypycli:\n  hello: "world"\n', encoding="utf-8"
    )
    t = Translator(d)
    app = _make_app(tmp_path, t)
    app.start()
    assert _i18n_internal._("hello") == "world"

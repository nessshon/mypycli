from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from mypycli.i18n.translator import Translator

if TYPE_CHECKING:
    from pathlib import Path


def _write(directory: Path, name: str, content: str) -> None:
    (directory / name).write_text(content, encoding="utf-8")


def test_init_scans_available_languages(tmp_path: Path) -> None:
    _write(tmp_path, "en.yml", "mypycli: {}\n")
    _write(tmp_path, "ru.yml", "mypycli: {}\n")
    _write(tmp_path, "README.md", "ignore me")
    t = Translator(tmp_path)
    assert t.available_languages() == {"en", "ru"}


def test_init_empty_dir(tmp_path: Path) -> None:
    t = Translator(tmp_path)
    assert t.available_languages() == set()


def test_init_missing_dir(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        Translator(tmp_path / "nope")


def test_language_none_before_set(tmp_path: Path) -> None:
    _write(tmp_path, "en.yml", "mypycli: {}\n")
    t = Translator(tmp_path)
    assert t.language is None


def test_available_languages_is_copy(tmp_path: Path) -> None:
    _write(tmp_path, "en.yml", "mypycli: {}\n")
    t = Translator(tmp_path)
    langs = t.available_languages()
    langs.add("xx")
    assert t.available_languages() == {"en"}


def test_set_language_loads_catalog(tmp_path: Path) -> None:
    _write(tmp_path, "en.yml", 'mypycli:\n  welcome: "Hi"\n')
    t = Translator(tmp_path)
    t.set_language("en")
    assert t.language == "en"
    assert t("mypycli.welcome") == "Hi"


def test_set_language_invalid(tmp_path: Path) -> None:
    _write(tmp_path, "en.yml", "mypycli: {}\n")
    t = Translator(tmp_path)
    with pytest.raises(ValueError, match="not available"):
        t.set_language("ru")


def test_set_language_switch_reloads(tmp_path: Path) -> None:
    _write(tmp_path, "en.yml", 'greeting: "Hello"\n')
    _write(tmp_path, "ru.yml", 'greeting: "Привет"\n')
    t = Translator(tmp_path)
    t.set_language("en")
    assert t("greeting") == "Hello"
    t.set_language("ru")
    assert t("greeting") == "Привет"


def test_call_before_set_language(tmp_path: Path) -> None:
    _write(tmp_path, "en.yml", 'mypycli:\n  x: "y"\n')
    t = Translator(tmp_path)
    with pytest.raises(RuntimeError, match="not initialized"):
        t("mypycli.x")


def test_call_missing_key(tmp_path: Path) -> None:
    _write(tmp_path, "en.yml", 'mypycli:\n  x: "y"\n')
    t = Translator(tmp_path)
    t.set_language("en")
    with pytest.raises(LookupError, match="Missing translation"):
        t("mypycli.unknown")


def test_call_format_kwargs(tmp_path: Path) -> None:
    _write(tmp_path, "en.yml", 'greeting: "Hi {name}!"\n')
    t = Translator(tmp_path)
    t.set_language("en")
    assert t("greeting", name="Alice") == "Hi Alice!"


def test_call_format_extra_kwargs_ignored(tmp_path: Path) -> None:
    _write(tmp_path, "en.yml", 'msg: "fixed"\n')
    t = Translator(tmp_path)
    t.set_language("en")
    assert t("msg", unused="x") == "fixed"


def test_call_format_missing_kwarg(tmp_path: Path) -> None:
    _write(tmp_path, "en.yml", 'msg: "Hi {name}"\n')
    t = Translator(tmp_path)
    t.set_language("en")
    with pytest.raises(KeyError):
        t("msg", other="x")


def test_call_no_kwargs_returns_as_is(tmp_path: Path) -> None:
    _write(tmp_path, "en.yml", 'msg: "plain {braces}"\n')
    t = Translator(tmp_path)
    t.set_language("en")
    assert t("msg") == "plain {braces}"

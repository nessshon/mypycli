from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from mypycli.i18n import internal
from mypycli.i18n.translator import Translator

if TYPE_CHECKING:
    from pathlib import Path


def _reset() -> None:
    internal._active = None


def test_underscore_before_bind_raises() -> None:
    _reset()
    with pytest.raises(RuntimeError, match="Translator not bound"):
        internal._("something")


def test_underscore_after_bind_returns_translated(tmp_path: Path) -> None:
    (tmp_path / "en.yml").write_text(
        'mypycli:\n  welcome: "Hello {name}"\n', encoding="utf-8"
    )
    t = Translator(tmp_path)
    t.set_language("en")
    internal.bind(t)
    try:
        assert internal._("welcome", name="World") == "Hello World"
    finally:
        _reset()


def test_underscore_auto_prefixes_mypycli(tmp_path: Path) -> None:
    (tmp_path / "en.yml").write_text(
        'mypycli:\n  only_library: "ok"\nuser_top_level: "user-owned"\n',
        encoding="utf-8",
    )
    t = Translator(tmp_path)
    t.set_language("en")
    internal.bind(t)
    try:
        assert internal._("only_library") == "ok"
        with pytest.raises(LookupError):
            internal._("user_top_level")
    finally:
        _reset()


def test_bind_replaces_previous_translator(tmp_path: Path) -> None:
    (tmp_path / "en.yml").write_text('mypycli:\n  k: "first"\n', encoding="utf-8")
    t1 = Translator(tmp_path)
    t1.set_language("en")
    internal.bind(t1)
    assert internal._("k") == "first"

    dir2 = tmp_path / "other"
    dir2.mkdir()
    (dir2 / "en.yml").write_text('mypycli:\n  k: "second"\n', encoding="utf-8")
    t2 = Translator(dir2)
    t2.set_language("en")
    internal.bind(t2)
    try:
        assert internal._("k") == "second"
    finally:
        _reset()

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from mypycli.i18n import Translator
from mypycli.i18n import internal as _i18n_internal

if TYPE_CHECKING:
    from collections.abc import Iterator


_LIB_LOCALES = Path(__file__).resolve().parent.parent / "mypycli" / "i18n" / "locales"


@pytest.fixture
def translator(tmp_path: Path) -> Translator:
    """A Translator pointing at a minimal tmp locales dir with en.yml."""
    d = tmp_path / "_shared_locales"
    d.mkdir()
    (d / "en.yml").write_text("mypycli: {}\n", encoding="utf-8")
    return Translator(d)


@pytest.fixture(autouse=True)
def _reset_i18n_internal() -> Iterator[None]:
    """Bind the real library catalog so library-internal ``_`` works in every test.

    ``mypycli/console/*`` call ``mypycli.i18n.internal._`` which requires a process-wide
    bound Translator. Tests that exercise console handlers directly (without going
    through ``app.start()``) would otherwise hit ``RuntimeError("Translator not bound")``.
    The state is reset between tests to avoid leakage.
    """
    t = Translator(_LIB_LOCALES)
    t.set_language("en")
    _i18n_internal.bind(t)
    yield
    _i18n_internal._active = None

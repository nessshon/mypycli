from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mypycli.i18n.translator import Translator

_active: Translator | None = None


def bind(translator: Translator) -> None:
    """Register the process-wide Translator used by the library-internal ``_``."""
    global _active
    _active = translator


def _(key: str, **kwargs: object) -> str:
    """Library-internal translator shortcut; auto-prefixes keys with ``mypycli.``."""
    if _active is None:
        raise RuntimeError("Translator not bound — did you call app.start()?")
    return _active(f"mypycli.{key}", **kwargs)

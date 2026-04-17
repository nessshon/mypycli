from __future__ import annotations

from pathlib import Path

from mypycli.i18n.loader import load_flat


class Translator:
    """Per-process i18n engine: eager-loads one language catalog on demand."""

    def __init__(self, locales_dir: Path | str) -> None:
        self._dir = Path(locales_dir)
        if not self._dir.is_dir():
            raise FileNotFoundError(f"Locales directory not found: {self._dir}")
        self._available: set[str] = {p.stem for p in self._dir.glob("*.yml")}
        self._catalog: dict[str, str] | None = None
        self._language: str | None = None

    def available_languages(self) -> set[str]:
        """Return a copy of the set of available language codes."""
        return set(self._available)

    @property
    def language(self) -> str | None:
        """Currently active language code, or None if not set."""
        return self._language

    @property
    def locales_dir(self) -> Path:
        """Directory containing the `*.yml` catalog files."""
        return self._dir

    def set_language(self, lang: str) -> None:
        """Load the catalog for `lang` and make it the active language."""
        if lang not in self._available:
            raise ValueError(
                f"Language '{lang}' not available. Available: {sorted(self._available)}"
            )
        self._catalog = load_flat(self._dir / f"{lang}.yml")
        self._language = lang

    def __call__(self, key: str, **kwargs: object) -> str:
        """Look up `key` in the active catalog and format with `kwargs` if given."""
        if self._catalog is None:
            raise RuntimeError("Translator not initialized — call set_language() first")
        tmpl = self._catalog.get(key)
        if tmpl is None:
            raise LookupError(f"Missing translation: '{key}' for lang '{self._language}'")
        return tmpl.format(**kwargs) if kwargs else tmpl

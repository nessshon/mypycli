from pathlib import Path

import pytest

from mypycli.components.translator import Translator


@pytest.fixture()
def app_locales(tmp_path: Path) -> Path:
    locales = tmp_path / "locales"
    locales.mkdir()
    (locales / "en.yml").write_text(
        'app:\n  greeting: "Hello, {name}!"\nmypycli:\n  message:\n    welcome: "App override"\n',
        encoding="utf-8",
    )
    (locales / "ru.yml").write_text('app:\n  greeting: "Привет, {name}!"\n', encoding="utf-8")
    return locales


class TestTranslator:
    def test_bundled_defaults_available_without_app_key(self, app_locales: Path) -> None:
        translator = Translator(app_locales, "en")
        assert translator("mypycli.commands.status") == "Show current status"

    def test_app_keys_resolve(self, app_locales: Path) -> None:
        translator = Translator(app_locales, "en")
        assert translator("app.greeting", name="TON") == "Hello, TON!"

    def test_app_overrides_bundled_key(self, app_locales: Path) -> None:
        translator = Translator(app_locales, "en")
        assert translator("mypycli.message.welcome") == "App override"

    def test_bundled_only_language_works_without_app_file(self, tmp_path: Path) -> None:
        empty = tmp_path / "locales"
        empty.mkdir()
        translator = Translator(empty, "zh")
        assert translator("mypycli.commands.exit")

    def test_set_language_switches_catalog(self, app_locales: Path) -> None:
        translator = Translator(app_locales, "en")
        translator.set_language("ru")
        assert translator("app.greeting", name="TON") == "Привет, TON!"

    def test_missing_key_raises(self, app_locales: Path) -> None:
        translator = Translator(app_locales, "en")
        with pytest.raises(KeyError):
            translator("app.no_such_key")

    def test_unknown_language_without_any_file_raises(self, app_locales: Path) -> None:
        with pytest.raises(FileNotFoundError):
            Translator(app_locales, "fr")

    def test_missing_locales_dir_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            Translator(tmp_path / "nope", "en")

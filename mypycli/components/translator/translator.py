from importlib.resources import files
from pathlib import Path

from mypycli.components.translator.loader import flatten_yaml, load_yaml


class Translator:
    def __init__(self, locales_dir: str | Path, language_code: str) -> None:
        self.locales_dir = Path(locales_dir)
        if not self.locales_dir.is_dir():
            raise FileNotFoundError(f"Locales dir not found: {self.locales_dir}")

        self.catalog: dict[str, str] = {}
        self.language_code = language_code
        self.set_language(self.language_code)

    def set_language(self, language_code: str) -> None:
        catalog = self._load_bundled(language_code)

        app_path = self.locales_dir / f"{language_code}.yml"
        if app_path.is_file():
            catalog.update(load_yaml(app_path))
        elif not catalog:
            raise FileNotFoundError(f"Locale file not found: {app_path}")

        self.catalog = catalog
        self.language_code = language_code

    def __call__(self, key: str, **kwargs: object) -> str:
        text = self.catalog.get(key)
        if text is None:
            raise KeyError(f"Missing translation '{key}' for language '{self.language_code}'")

        return text.format(**kwargs) if kwargs else text

    @staticmethod
    def _load_bundled(language_code: str) -> dict[str, str]:
        resource = files("mypycli").joinpath(f"components/translator/locales/{language_code}.yml")
        if not resource.is_file():
            return {}
        return flatten_yaml(resource.read_text(encoding="utf-8"), source=str(resource))

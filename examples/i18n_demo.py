from __future__ import annotations

from pathlib import Path

from mypycli import Application, DatabaseSchema, Translator

_BUNDLED_LOCALES = Path(__file__).parent / "locales"


def main() -> None:
    translator = Translator(_BUNDLED_LOCALES)
    app = Application(
        db_schema=DatabaseSchema,
        work_dir=Path(__file__).parent / "_demo_data",
        name="demo",
        label="Demo App",
        translator=translator,
    )
    app.run()


if __name__ == "__main__":
    main()

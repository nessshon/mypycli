from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest

from mypycli.cli.commands.install import run_install
from mypycli.database import Database, DatabaseSchema
from mypycli.modules.interfaces.installable import Installable
from mypycli.modules.registry import ModuleRegistry

if TYPE_CHECKING:
    from pathlib import Path


class _Storage(Installable):
    name = "storage"

    def __init__(self, app: Any) -> None:
        super().__init__(app)
        self.installed = False

    def on_install(self) -> None:
        self.installed = True

    def on_uninstall(self) -> None:
        pass


class _Provider(Installable):
    name = "provider"

    def __init__(self, app: Any) -> None:
        super().__init__(app)
        self.installed = False
        self.saw_storage_path: str | None = None

    def on_install(self) -> None:
        # Provider can read sibling's persisted data directly.
        storage = self.app.modules.get("storage")
        self.saw_storage_path = getattr(storage, "recorded_path", None)
        self.installed = True

    def on_uninstall(self) -> None:
        pass


class _Raising(Installable):
    name = "boom"
    mandatory = True

    def on_install(self) -> None:
        raise RuntimeError("boom")

    def on_uninstall(self) -> None:
        pass


def _app(tmp_path: Path, *modules: type[Installable]) -> Any:
    app = MagicMock()
    app.name = "test"
    app.label = "Test"
    app.db = Database(DatabaseSchema, tmp_path / "t.db")
    app.start.side_effect = lambda: app.db.load(auto_create=True)
    registry = ModuleRegistry()
    for cls in modules:
        registry.register(cls(app))
    app.modules = registry
    app.console = MagicMock()
    return app


class TestRunInstall:
    def test_installs_selected_modules(self, tmp_path: Path) -> None:
        app = _app(tmp_path, _Storage, _Provider)
        run_install(app, selected=["storage", "provider"])
        assert app.modules.get("storage").installed is True
        assert app.modules.get("provider").installed is True

    def test_skips_not_selected_optional(self, tmp_path: Path) -> None:
        app = _app(tmp_path, _Storage, _Provider)
        run_install(app, selected=["storage"])
        assert app.modules.get("storage").installed is True
        assert app.modules.get("provider").installed is False

    def test_stops_on_first_failure(self, tmp_path: Path) -> None:
        app = _app(tmp_path, _Raising, _Storage)
        with pytest.raises(SystemExit) as exc:
            run_install(app, selected=["storage"])
        assert exc.value.code == 1
        # _Storage registered after _Raising; on_install should not have run
        assert app.modules.get("storage").installed is False

    def test_cross_module_access_via_registry(self, tmp_path: Path) -> None:
        class _A(Installable):
            name = "a"

            def on_install(self) -> None:
                self.recorded_path = "/data/a"

            def on_uninstall(self) -> None:
                pass

        class _B(Installable):
            name = "b"

            def __init__(self, app: Any) -> None:
                super().__init__(app)
                self.saw: str | None = None

            def on_install(self) -> None:
                a = self.app.modules.get("a")
                self.saw = a.recorded_path

            def on_uninstall(self) -> None:
                pass

        app = _app(tmp_path, _A, _B)
        run_install(app, selected=["a", "b"])
        assert app.modules.get("b").saw == "/data/a"

    def test_framework_writes_empty_key_when_module_has_no_db(self, tmp_path: Path) -> None:
        app = _app(tmp_path, _Storage)
        run_install(app, selected=["storage"])
        assert "storage" in app.db.installed_modules()

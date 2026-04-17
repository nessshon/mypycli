from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest

from mypycli.database import Database, DatabaseSchema
from mypycli.modules.base import Module
from mypycli.modules.interfaces.daemonic import Daemonic
from mypycli.modules.interfaces.installable import Installable
from mypycli.modules.registry import ModuleRegistry, build_modules

if TYPE_CHECKING:
    from pathlib import Path


class _Plain(Module):
    name = "plain"


class _Labeled(Module):
    name = "labeled"
    label = "Labeled Module"


class _Disabled(Module):
    name = "disabled"

    @property
    def is_enabled(self) -> bool:
        return False


class _DaemonicMod(Daemonic):
    name = "dmod"

    def on_daemon(self) -> None:
        pass


class _InstallableMod(Installable):
    name = "imod"

    def on_install(self) -> None:
        pass

    def on_uninstall(self) -> None:
        pass


class TestModuleBase:
    def test_display_name_falls_back_to_name(self) -> None:
        app = MagicMock()
        assert _Plain(app).display_name == "plain"
        assert _Labeled(app).display_name == "Labeled Module"

    def test_subclass_without_name_raises(self) -> None:
        with pytest.raises(TypeError, match="non-empty 'name'"):

            class _Bad(Module):
                pass

    def test_subclass_with_empty_name_raises(self) -> None:
        with pytest.raises(TypeError, match="non-empty 'name'"):

            class _BadEmpty(Module):
                name = ""

    def test_subclass_with_uppercase_name_raises(self) -> None:
        with pytest.raises(TypeError, match=r"\[a-z0-9\]\[a-z0-9_-\]"):

            class _Upper(Module):
                name = "TonStorage"

    def test_subclass_with_space_in_name_raises(self) -> None:
        with pytest.raises(TypeError, match=r"\[a-z0-9\]\[a-z0-9_-\]"):

            class _Spaces(Module):
                name = "ton storage"

    def test_subclass_with_leading_dash_raises(self) -> None:
        with pytest.raises(TypeError, match=r"\[a-z0-9\]\[a-z0-9_-\]"):

            class _LeadingDash(Module):
                name = "-storage"


class TestModuleRunTask:
    def _mod_with_worker(self) -> tuple[_Plain, MagicMock]:
        app = MagicMock()
        app.worker.add = MagicMock(side_effect=lambda task: task)
        return _Plain(app), app.worker.add

    def test_run_task_composes_name_and_starts(self) -> None:
        mod, add = self._mod_with_worker()

        def boot() -> None:
            pass

        task = mod.run_task(boot)
        try:
            assert task.name == "plain.boot"
            add.assert_called_once_with(task)
        finally:
            task.stop()
            task.wait(timeout=1)

    def test_run_task_suffix_overrides_func_name(self) -> None:
        mod, _ = self._mod_with_worker()

        def boot() -> None:
            pass

        task = mod.run_task(boot, suffix="warmup")
        try:
            assert task.name == "plain.warmup"
        finally:
            task.stop()
            task.wait(timeout=1)

    def test_run_cycle_composes_name_and_applies_interval(self) -> None:
        mod, add = self._mod_with_worker()

        def tick() -> None:
            pass

        task = mod.run_cycle(tick, seconds=0.01)
        try:
            assert task.name == "plain.tick"
            add.assert_called_once_with(task)
        finally:
            task.stop()
            task.wait(timeout=1)


def _mock_app_unloaded() -> Any:
    app = MagicMock()
    app.db.is_loaded = False  # pre-load: default is_enabled=True
    return app


class TestModuleRegistry:
    def _reg(self, *classes: type[Module]) -> ModuleRegistry:
        reg = ModuleRegistry()
        app = _mock_app_unloaded()
        for cls in classes:
            reg.register(cls(app))
        return reg

    def test_register_and_get(self) -> None:
        reg = self._reg(_Plain)
        assert reg.get("plain").name == "plain"

    def test_duplicate_name_raises(self) -> None:
        reg = self._reg(_Plain)
        with pytest.raises(ValueError, match="Duplicate"):
            reg.register(_Plain(_mock_app_unloaded()))

    def test_get_unknown_raises(self) -> None:
        with pytest.raises(KeyError):
            ModuleRegistry().get("nope")

    def test_all_default_skips_disabled(self) -> None:
        reg = self._reg(_Plain, _Disabled)
        assert {m.name for m in reg.all()} == {"plain"}
        assert {m.name for m in reg.all(enabled_only=False)} == {"plain", "disabled"}

    def test_by_interface_skips_disabled(self) -> None:
        reg = self._reg(_DaemonicMod, _InstallableMod)
        daemons = reg.by_interface(Daemonic)
        assert [m.name for m in daemons] == ["dmod"]

    def test_get_by_class(self) -> None:
        reg = self._reg(_DaemonicMod)
        assert reg.get_by_class(_DaemonicMod).name == "dmod"
        with pytest.raises(KeyError):
            reg.get_by_class(_Plain)


class _StorageDB(DatabaseSchema):
    storage_path: str = "/var/default"
    port: int = 8080


class _NestedDB(DatabaseSchema):
    outer: str = ""
    inner: _StorageDB = _StorageDB()


class _WithDB(Module):
    name = "with_db"
    db_schema = _StorageDB


class _WithNestedDB(Module):
    name = "with_nested"
    db_schema = _NestedDB


class _WithoutDB(Module):
    name = "without_db"


class _Mandatory(Module):
    name = "mand"
    mandatory = True


class _InstOpt(Installable):
    name = "opt_inst"
    mandatory = False

    def on_install(self) -> None:
        pass

    def on_uninstall(self) -> None:
        pass


class _InstMand(Installable):
    name = "mand_inst"
    mandatory = True

    def on_install(self) -> None:
        pass

    def on_uninstall(self) -> None:
        pass


def _mk_app(tmp_path: Path) -> Any:
    app = MagicMock()
    app.name = "testapp"
    app.db = Database(DatabaseSchema, tmp_path / "db.json")
    app.db.load(auto_create=True)
    return app


class TestModuleDB:
    def test_no_schema_raises_type_error(self, tmp_path: Path) -> None:
        app = _mk_app(tmp_path)
        mod = _WithoutDB(app)
        with pytest.raises(TypeError, match="no db_schema"):
            _ = mod.db

    def test_access_before_load_raises_runtime_error(self, tmp_path: Path) -> None:
        app = MagicMock()
        app.name = "testapp"
        app.db = Database(DatabaseSchema, tmp_path / "db.json")
        mod = _WithDB(app)
        with pytest.raises(RuntimeError, match=r"before Database\.load"):
            _ = mod.db

    def test_reads_defaults_when_no_stored_data(self, tmp_path: Path) -> None:
        app = _mk_app(tmp_path)
        mod = _WithDB(app)
        assert mod.db.storage_path == "/var/default"
        assert mod.db.port == 8080

    def test_reads_stored_data(self, tmp_path: Path) -> None:
        app = _mk_app(tmp_path)
        app.db.set_module_data("with_db", {"storage_path": "/data", "port": 9999})
        mod = _WithDB(app)
        assert mod.db.storage_path == "/data"
        assert mod.db.port == 9999

    def test_assignment_triggers_auto_save(self, tmp_path: Path) -> None:
        app = _mk_app(tmp_path)
        mod = _WithDB(app)
        mod.db.storage_path = "/custom"

        raw = json.loads((tmp_path / "db.json").read_text())
        # Only the touched field is persisted; defaults live in the schema.
        assert raw["modules"]["with_db"] == {"storage_path": "/custom"}

    def test_cache_reuses_instance(self, tmp_path: Path) -> None:
        app = _mk_app(tmp_path)
        mod = _WithDB(app)
        first = mod.db
        second = mod.db
        assert first is second

    def test_nested_schema_auto_save(self, tmp_path: Path) -> None:
        app = _mk_app(tmp_path)
        mod = _WithNestedDB(app)
        mod.db.inner.port = 12345

        raw = json.loads((tmp_path / "db.json").read_text())
        assert raw["modules"]["with_nested"]["inner"]["port"] == 12345

    def test_cross_module_shared_access(self, tmp_path: Path) -> None:
        app = _mk_app(tmp_path)
        registry = ModuleRegistry()
        app.modules = registry
        mod_a = _WithDB(app)
        registry.register(mod_a)

        mod_a.db.storage_path = "/shared"

        same = registry.get_by_class(_WithDB)
        assert same.db.storage_path == "/shared"
        assert same.db is mod_a.db

    def test_installed_modules_reflects_db_writes(self, tmp_path: Path) -> None:
        app = _mk_app(tmp_path)
        mod = _WithDB(app)
        assert app.db.installed_modules() == []
        mod.db.storage_path = "/x"
        assert app.db.installed_modules() == ["with_db"]


class TestIsEnabled:
    def test_pre_load_returns_true(self, tmp_path: Path) -> None:
        app = MagicMock()
        app.db = Database(DatabaseSchema, tmp_path / "db.json")
        mod = _Plain(app)
        assert mod.is_enabled is True

    def test_loaded_no_key_returns_false(self, tmp_path: Path) -> None:
        app = _mk_app(tmp_path)
        mod = _Plain(app)
        assert mod.is_enabled is False

    def test_loaded_with_key_returns_true(self, tmp_path: Path) -> None:
        app = _mk_app(tmp_path)
        app.db.set_module_data("plain", {})
        mod = _Plain(app)
        assert mod.is_enabled is True

    def test_mandatory_non_installable_alone_is_not_enabled(self, tmp_path: Path) -> None:
        app = _mk_app(tmp_path)
        mod = _Mandatory(app)
        assert mod.is_enabled is False  # app.start() not called yet

    def test_custom_override_wins(self, tmp_path: Path) -> None:
        app = _mk_app(tmp_path)
        mod = _Disabled(app)
        assert mod.is_enabled is False  # explicit override


class TestByInterfaceEnabledFlag:
    def test_default_filters_enabled(self, tmp_path: Path) -> None:
        app = _mk_app(tmp_path)
        app.db.set_module_data("mand_inst", {})
        reg = ModuleRegistry()
        reg.register(_InstMand(app))
        reg.register(_InstOpt(app))
        # mand_inst has key → enabled; opt_inst has no key → disabled
        names = [m.name for m in reg.by_interface(Installable)]
        assert names == ["mand_inst"]

    def test_disabled_flag_returns_all(self, tmp_path: Path) -> None:
        app = _mk_app(tmp_path)
        reg = ModuleRegistry()
        reg.register(_InstMand(app))
        reg.register(_InstOpt(app))
        # Neither installed, enabled_only=False still returns both
        names = [m.name for m in reg.by_interface(Installable, enabled_only=False)]
        assert set(names) == {"mand_inst", "opt_inst"}


class TestBuildModules:
    def test_instantiates_and_binds_to_app(self) -> None:
        app = MagicMock()
        registry = build_modules(app, [_Plain, _DaemonicMod])
        assert app.modules is registry
        assert {m.name for m in registry.all(enabled_only=False)} == {"plain", "dmod"}

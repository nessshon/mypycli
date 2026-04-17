from __future__ import annotations

import json
import threading
from typing import TYPE_CHECKING

import pytest

from mypycli.database import Database, DatabaseSchema
from mypycli.database.schema import _wire_model

if TYPE_CHECKING:
    from pathlib import Path


class _Schema(DatabaseSchema):
    name: str = "default"
    count: int = 0


class _NestedInner(DatabaseSchema):
    value: int = 0


class _NestedSchema(DatabaseSchema):
    inner: _NestedInner = _NestedInner()
    label: str = ""


def _db(tmp_path: Path, schema: type[DatabaseSchema] = _Schema) -> Database:
    db = Database(schema, tmp_path / "db.json")
    db.load(auto_create=True)
    return db


class TestLoadSave:
    def test_auto_create_writes_defaults(self, tmp_path: Path) -> None:
        _db(tmp_path)
        raw = json.loads((tmp_path / "db.json").read_text())
        assert raw == {"debug": False, "language": "", "name": "default", "count": 0}
        # "debug" and "language" live in extras — framework writes them on first auto_create

    def test_load_missing_file_raises(self, tmp_path: Path) -> None:
        db = Database(_Schema, tmp_path / "nope.json")
        with pytest.raises(FileNotFoundError):
            db.load()

    def test_load_preserves_extras(self, tmp_path: Path) -> None:
        path = tmp_path / "db.json"
        path.write_text(json.dumps({"name": "x", "count": 1, "legacy_field": 42}))
        db = Database(_Schema, path)
        db.load()
        assert db.data.name == "x"
        assert db.get_extra("legacy_field") == 42

    def test_save_round_trip(self, tmp_path: Path) -> None:
        db = _db(tmp_path)
        db.data.name = "changed"
        db.data.count = 99

        db2 = Database(_Schema, tmp_path / "db.json")
        db2.load()
        assert db2.data.name == "changed"
        assert db2.data.count == 99

    def test_save_preserves_foreign_writer_keys(self, tmp_path: Path) -> None:
        path = tmp_path / "db.json"
        db = _db(tmp_path)

        raw = json.loads(path.read_text())
        raw["foreign"] = "added_externally"
        path.write_text(json.dumps(raw))

        db.data.name = "updated"

        merged = json.loads(path.read_text())
        assert merged["name"] == "updated"
        assert merged["foreign"] == "added_externally"


class TestAutoSave:
    def test_field_assignment_persists_immediately(self, tmp_path: Path) -> None:
        db = _db(tmp_path)
        db.data.name = "auto"

        raw = json.loads((tmp_path / "db.json").read_text())
        assert raw["name"] == "auto"

    def test_nested_field_assignment_persists(self, tmp_path: Path) -> None:
        db = _db(tmp_path, _NestedSchema)
        db.data.inner.value = 42

        raw = json.loads((tmp_path / "db.json").read_text())
        assert raw["inner"]["value"] == 42

    def test_replaced_nested_model_gets_callback(self, tmp_path: Path) -> None:
        db = _db(tmp_path, _NestedSchema)
        db.data.inner = _NestedInner(value=99)
        db.data.inner.value = 77

        raw = json.loads((tmp_path / "db.json").read_text())
        assert raw["inner"]["value"] == 77

    def test_no_save_before_load(self, tmp_path: Path) -> None:
        path = tmp_path / "db.json"
        db = Database(_Schema, path)
        db._data.name = "should_not_persist"
        assert not path.exists()


class TestAutoReload:
    def test_external_modification_detected(self, tmp_path: Path) -> None:
        db = _db(tmp_path)
        path = tmp_path / "db.json"

        raw = json.loads(path.read_text())
        raw["name"] = "external"
        path.write_text(json.dumps(raw))

        assert db.data.name == "external"

    def test_no_reload_when_unchanged(self, tmp_path: Path) -> None:
        db = _db(tmp_path)
        db.data.name = "set_once"

        data_obj = db._data
        _ = db.data
        assert db._data is data_obj

    def test_corrupt_json_keeps_current_data(self, tmp_path: Path) -> None:
        db = _db(tmp_path)
        db.data.name = "valid"
        path = tmp_path / "db.json"

        path.write_text("NOT JSON {{{")

        assert db.data.name == "valid"

    def test_corrupt_json_warns_to_provided_logger(self, tmp_path: Path) -> None:
        import logging

        logger = logging.getLogger("test-db-logger")
        logger.handlers.clear()
        records: list[logging.LogRecord] = []
        logger.addHandler(type("H", (logging.Handler,), {"emit": lambda self, r: records.append(r)})())

        db = Database(_Schema, tmp_path / "db.json", logger=logger)
        db.load(auto_create=True)
        db.data.name = "valid"
        (tmp_path / "db.json").write_text("NOT JSON {{{")
        _ = db.data

        assert any("Corrupt JSON" in r.getMessage() for r in records)

    def test_corrupt_json_healed_by_save(self, tmp_path: Path) -> None:
        db = _db(tmp_path)
        db.data.name = "good"
        path = tmp_path / "db.json"

        path.write_text("")

        db.data.count = 42

        raw = json.loads(path.read_text())
        assert raw["name"] == "good"
        assert raw["count"] == 42

    def test_extras_refreshed_on_reload(self, tmp_path: Path) -> None:
        db = _db(tmp_path)
        path = tmp_path / "db.json"

        raw = json.loads(path.read_text())
        raw["new_extra"] = "hello"
        path.write_text(json.dumps(raw))

        assert db.get_extra("new_extra") == "hello"


class TestExtras:
    def test_set_get_del(self, tmp_path: Path) -> None:
        db = _db(tmp_path)
        db.set_extra("foo", {"bar": 1})
        assert db.get_extra("foo") == {"bar": 1}
        db.del_extra("foo")
        assert db.get_extra("foo") is None

    def test_set_extra_persists_immediately(self, tmp_path: Path) -> None:
        db = _db(tmp_path)
        db.set_extra("key", "val")

        raw = json.loads((tmp_path / "db.json").read_text())
        assert raw["key"] == "val"

    def test_del_extra_persists_immediately(self, tmp_path: Path) -> None:
        path = tmp_path / "db.json"
        path.write_text(json.dumps({"name": "x", "count": 0, "old_key": "remove_me"}))

        db = Database(_Schema, path)
        db.load()
        db.del_extra("old_key")

        raw = json.loads(path.read_text())
        assert "old_key" not in raw

    def test_all_data_merges_schema_and_extras(self, tmp_path: Path) -> None:
        db = _db(tmp_path)
        db.set_extra("extra", "val")
        data = db.all_data()
        assert data["extra"] == "val"
        assert data["name"] == "default"


class TestGetSetByPath:
    def test_get_schema_field(self, tmp_path: Path) -> None:
        db = _db(tmp_path)
        db.data.name = "test"
        assert db.get_by_path("name") == (True, "test")

    def test_get_missing_path(self, tmp_path: Path) -> None:
        db = _db(tmp_path)
        assert db.get_by_path("nonexistent.deep.path") == (False, None)

    def test_set_schema_field(self, tmp_path: Path) -> None:
        db = _db(tmp_path)
        db.set_by_path("name", "new")
        assert db.data.name == "new"

    def test_set_schema_field_validates(self, tmp_path: Path) -> None:
        db = _db(tmp_path)
        with pytest.raises((ValueError, TypeError)):
            db.set_by_path("count", "not_a_number")

    def test_set_extra_flat(self, tmp_path: Path) -> None:
        db = _db(tmp_path)
        db.set_by_path("new_key", 123)
        assert db.get_extra("new_key") == 123

    def test_set_extra_persists_via_set_by_path(self, tmp_path: Path) -> None:
        db = _db(tmp_path)
        db.set_by_path("new_key", 123)

        raw = json.loads((tmp_path / "db.json").read_text())
        assert raw["new_key"] == 123

    def test_set_extra_nested_requires_existing_parent(self, tmp_path: Path) -> None:
        db = _db(tmp_path)
        with pytest.raises(KeyError):
            db.set_by_path("missing.nested.key", 1)

        db.set_extra("section", {"key": "old"})
        db.set_by_path("section.key", "new")
        assert db.get_extra("section") == {"key": "new"}

    def test_set_nested_schema(self, tmp_path: Path) -> None:
        db = _db(tmp_path, _NestedSchema)
        db.set_by_path("inner.value", 42)
        assert db.data.inner.value == 42

    def test_get_by_path_nested_extra(self, tmp_path: Path) -> None:
        path = tmp_path / "db.json"
        path.write_text(json.dumps({"name": "x", "count": 0, "meta": {"version": 2}}))
        db = Database(_Schema, path)
        db.load()
        assert db.get_by_path("meta.version") == (True, 2)


class TestSetByPathStr:
    def test_json_decoded_into_schema(self, tmp_path: Path) -> None:
        db = _db(tmp_path)
        db.set_by_path_str("name", '"alice"')
        db.set_by_path_str("count", "42")
        assert db.data.name == "alice"
        assert db.data.count == 42

    def test_json_bool(self, tmp_path: Path) -> None:
        class _BoolSchema(DatabaseSchema):
            flag: bool = False

        db = _db(tmp_path, _BoolSchema)
        db.set_by_path_str("flag", "true")
        assert db.data.flag is True

    def test_bool_aliases_case_insensitive(self, tmp_path: Path) -> None:
        db = _db(tmp_path)
        for raw in ("true", "True", "TRUE", " true "):
            db.set_by_path_str("some_flag", raw)
            assert db.get_extra("some_flag") is True
        for raw in ("false", "False", "FALSE", " FALSE"):
            db.set_by_path_str("some_flag", raw)
            assert db.get_extra("some_flag") is False

    def test_bool_alias_for_extras_debug(self, tmp_path: Path) -> None:
        db = _db(tmp_path)
        db.set_by_path_str("debug", "True")
        assert db.debug is True
        db.set_by_path_str("debug", "False")
        assert db.debug is False

    def test_bare_string_fallback(self, tmp_path: Path) -> None:
        db = _db(tmp_path)
        db.set_by_path_str("name", "foo")
        assert db.data.name == "foo"

    def test_json_object_into_extras(self, tmp_path: Path) -> None:
        db = _db(tmp_path, _NestedSchema)
        db.set_extra("meta", {"version": 1})
        db.set_by_path_str("meta", '{"version": 5}')
        assert db.get_extra("meta") == {"version": 5}

    def test_invalid_type_raises(self, tmp_path: Path) -> None:
        db = _db(tmp_path)
        with pytest.raises((ValueError, TypeError)):
            db.set_by_path_str("count", "abc")


class TestSchemaAutoSave:
    def test_schema_triggers_callback_on_assignment(self) -> None:
        class _S(DatabaseSchema):
            name: str = ""

        s = _S()
        calls: list[int] = []
        _wire_model(s, lambda: calls.append(1))
        s.name = "x"
        assert calls == [1]

    def test_schema_no_callback_wire_no_save(self) -> None:
        class _S(DatabaseSchema):
            name: str = ""

        s = _S()
        s.name = "x"
        assert s.name == "x"


class TestDatabaseProxy:
    def test_proxy_read_schema_field(self, tmp_path: Path) -> None:
        db = _db(tmp_path)
        assert db.name == "default"
        assert db.count == 0

    def test_proxy_write_schema_field_persists(self, tmp_path: Path) -> None:
        db = _db(tmp_path)
        db.name = "proxy_write"
        assert db.data.name == "proxy_write"

        raw = json.loads((tmp_path / "db.json").read_text())
        assert raw["name"] == "proxy_write"

    def test_proxy_read_unknown_raises_attribute_error(self, tmp_path: Path) -> None:
        db = _db(tmp_path)
        with pytest.raises(AttributeError):
            _ = db.nonexistent

    def test_proxy_write_unknown_sets_instance_attr(self, tmp_path: Path) -> None:
        db = _db(tmp_path)
        db.custom_attr = 42
        assert db.custom_attr == 42
        raw = json.loads((tmp_path / "db.json").read_text())
        assert "custom_attr" not in raw

    def test_proxy_does_not_shadow_methods(self, tmp_path: Path) -> None:
        db = _db(tmp_path)
        assert callable(db.load)
        assert callable(db.save)
        assert callable(db.get_extra)


class TestIsLoaded:
    def test_not_loaded_before_load(self, tmp_path: Path) -> None:
        db = Database(_Schema, tmp_path / "db.json")
        assert db.is_loaded is False

    def test_loaded_after_auto_create(self, tmp_path: Path) -> None:
        db = _db(tmp_path)
        assert db.is_loaded is True

    def test_loaded_after_load(self, tmp_path: Path) -> None:
        path = tmp_path / "db.json"
        path.write_text(json.dumps({"name": "x", "count": 0}))
        db = Database(_Schema, path)
        db.load()
        assert db.is_loaded is True


class TestModuleData:
    def test_set_get(self, tmp_path: Path) -> None:
        db = _db(tmp_path)
        db.set_module_data("mod-a", {"key": 1})
        assert db.get_module_data("mod-a") == {"key": 1}

    def test_get_missing_returns_empty_dict(self, tmp_path: Path) -> None:
        db = _db(tmp_path)
        assert db.get_module_data("unknown") == {}

    def test_get_returns_copy(self, tmp_path: Path) -> None:
        db = _db(tmp_path)
        db.set_module_data("mod-a", {"key": 1})
        data = db.get_module_data("mod-a")
        data["key"] = 999
        assert db.get_module_data("mod-a") == {"key": 1}

    def test_set_persists_under_modules_key(self, tmp_path: Path) -> None:
        db = _db(tmp_path)
        db.set_module_data("mod-a", {"x": "y"})
        raw = json.loads((tmp_path / "db.json").read_text())
        assert raw["modules"] == {"mod-a": {"x": "y"}}

    def test_installed_modules_empty(self, tmp_path: Path) -> None:
        db = _db(tmp_path)
        assert db.installed_modules() == []

    def test_installed_modules_after_set(self, tmp_path: Path) -> None:
        db = _db(tmp_path)
        db.set_module_data("mod-a", {})
        db.set_module_data("mod-b", {"x": 1})
        assert set(db.installed_modules()) == {"mod-a", "mod-b"}

    def test_del_removes_module(self, tmp_path: Path) -> None:
        db = _db(tmp_path)
        db.set_module_data("mod-a", {"x": 1})
        db.set_module_data("mod-b", {"y": 2})
        db.del_module_data("mod-a")
        assert db.installed_modules() == ["mod-b"]

    def test_del_missing_is_noop(self, tmp_path: Path) -> None:
        db = _db(tmp_path)
        db.del_module_data("unknown")
        assert db.installed_modules() == []

    def test_del_last_removes_modules_key(self, tmp_path: Path) -> None:
        db = _db(tmp_path)
        db.set_module_data("mod-a", {"x": 1})
        db.del_module_data("mod-a")
        raw = json.loads((tmp_path / "db.json").read_text())
        assert "modules" not in raw


class TestLanguage:
    def test_default_empty_after_load(self, tmp_path: Path) -> None:
        db = Database(DatabaseSchema, tmp_path / "db.json")
        db.load(auto_create=True)
        assert db.language == ""

    def test_setter_persists(self, tmp_path: Path) -> None:
        db = Database(DatabaseSchema, tmp_path / "db.json")
        db.load(auto_create=True)
        db.language = "ru"
        assert db.language == "ru"

        db2 = Database(DatabaseSchema, tmp_path / "db.json")
        db2.load()
        assert db2.language == "ru"

    def test_setter_coerces_to_str(self, tmp_path: Path) -> None:
        db = Database(DatabaseSchema, tmp_path / "db.json")
        db.load(auto_create=True)
        db.language = 42  # type: ignore[assignment]
        assert db.language == "42"

    def test_empty_string_does_not_round_trip_as_none(self, tmp_path: Path) -> None:
        db = Database(DatabaseSchema, tmp_path / "db.json")
        db.load(auto_create=True)
        db.language = "en"
        db.language = ""
        assert db.language == ""


class TestThreadSafety:
    def test_concurrent_save_does_not_corrupt_file(self, tmp_path: Path) -> None:
        db = _db(tmp_path)
        errors: list[Exception] = []

        def writer(n: int) -> None:
            try:
                for i in range(20):
                    db.data.count = n * 100 + i
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=writer, args=(t,)) for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        raw = json.loads((tmp_path / "db.json").read_text())
        assert isinstance(raw["count"], int)

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from mypycli.application import Application
from mypycli.database import DatabaseSchema
from mypycli.modules.base import Module
from mypycli.modules.interfaces.installable import Installable

if TYPE_CHECKING:
    from pathlib import Path

    from mypycli.i18n import Translator


class _InstallMod(Installable):
    name = "imod"

    def on_install(self) -> None:
        pass

    def on_uninstall(self) -> None:
        pass


class _Plain(Module):
    name = "plain"


class _BadSchema(DatabaseSchema):
    pass


def test_construction_succeeds(tmp_path: Path, translator: Translator) -> None:
    app = Application(
        _BadSchema, tmp_path, name="a", modules=[_InstallMod], translator=translator
    )
    assert app.name == "a"
    assert app.modules.get("imod").name == "imod"


def test_construction_without_modules(tmp_path: Path, translator: Translator) -> None:
    app = Application(
        _BadSchema, tmp_path, name="a", modules=[_Plain], translator=translator
    )
    assert app.modules.get("plain").name == "plain"


def test_name_is_lowercased(tmp_path: Path, translator: Translator) -> None:
    app = Application(_BadSchema, tmp_path, name="MyApp", translator=translator)
    assert app.name == "myapp"
    assert app.label == "MyApp"


def test_env_prefix_defaults_to_none(tmp_path: Path, translator: Translator) -> None:
    app = Application(_BadSchema, tmp_path, name="a", translator=translator)
    assert app.env_prefix is None


def test_env_prefix_explicit_is_stored_as_is(
    tmp_path: Path, translator: Translator
) -> None:
    app = Application(
        _BadSchema,
        tmp_path,
        name="mytonprovider",
        env_prefix="MTP",
        translator=translator,
    )
    assert app.env_prefix == "MTP"


def test_pid_lifecycle(tmp_path: Path, translator: Translator) -> None:
    app = Application(_BadSchema, tmp_path, name="a", translator=translator)
    assert not app.pid_path.exists()

    app.write_pid()
    assert app.pid_path.exists()
    assert int(app.pid_path.read_text()) == os.getpid()

    app.remove_pid()
    assert not app.pid_path.exists()


def test_is_running_without_pid_file(tmp_path: Path, translator: Translator) -> None:
    app = Application(_BadSchema, tmp_path, name="a", translator=translator)
    running, pid = app.is_running()
    assert running is False
    assert pid is None


def test_is_running_with_current_pid(tmp_path: Path, translator: Translator) -> None:
    app = Application(_BadSchema, tmp_path, name="a", translator=translator)
    app.write_pid()
    running, pid = app.is_running()
    assert running is True
    assert pid == os.getpid()
    app.remove_pid()


def test_is_running_with_stale_pid(tmp_path: Path, translator: Translator) -> None:
    app = Application(_BadSchema, tmp_path, name="a", translator=translator)
    app.pid_path.write_text("999999", encoding="utf-8")
    running, pid = app.is_running()
    assert running is False
    assert pid == 999999


def test_start_loads_db(tmp_path: Path, translator: Translator) -> None:
    app = Application(_BadSchema, tmp_path, name="a", translator=translator)
    app.start()
    try:
        assert app.db.path.exists()
    finally:
        app.stop()


def test_start_does_not_write_pid(tmp_path: Path, translator: Translator) -> None:
    app = Application(_BadSchema, tmp_path, name="a", translator=translator)
    app.start()
    try:
        assert not app.pid_path.exists()
    finally:
        app.stop()


def test_debug_flag_raises_logger_level(
    tmp_path: Path, translator: Translator
) -> None:
    import json
    import logging

    (tmp_path / "a.db").write_text(json.dumps({"debug": True}))
    app = Application(_BadSchema, tmp_path, name="a", translator=translator)
    app.start()
    try:
        assert app.logger.level == logging.DEBUG
    finally:
        app.stop()


def test_paths(tmp_path: Path, translator: Translator) -> None:
    app = Application(_BadSchema, tmp_path, name="demo", translator=translator)
    assert app.pid_path == tmp_path / "demo.pid"
    assert app.log_path == tmp_path / "demo.log"
    assert app.db.path == tmp_path / "demo.db"


class _PlainA(Module):
    name = "plain-a"


class _PlainB(Module):
    name = "plain-b"


def test_start_writes_keys_for_non_installable_modules(
    tmp_path: Path, translator: Translator
) -> None:
    """Every non-Installable module is registered in db.modules on start()."""
    app = Application(
        _BadSchema,
        tmp_path,
        name="a",
        modules=[_PlainA, _PlainB],
        translator=translator,
    )
    app.start()
    try:
        installed = app.db.installed_modules()
        assert "plain-a" in installed
        assert "plain-b" in installed
    finally:
        app.stop()


def test_start_does_not_write_key_for_uninstalled_installable(
    tmp_path: Path, translator: Translator
) -> None:
    """Installable mandatory that hasn't run on_install stays out of db.modules."""
    app = Application(
        _BadSchema, tmp_path, name="a", modules=[_InstallMod], translator=translator
    )
    app.start()
    try:
        assert "imod" not in app.db.installed_modules()
    finally:
        app.stop()


def test_start_does_not_overwrite_existing_non_installable_data(
    tmp_path: Path, translator: Translator
) -> None:
    import json

    (tmp_path / "a.db").write_text(json.dumps({"modules": {"plain-a": {"kept": "value"}}}))
    app = Application(
        _BadSchema, tmp_path, name="a", modules=[_PlainA], translator=translator
    )
    app.start()
    try:
        assert app.db.get_module_data("plain-a") == {"kept": "value"}
    finally:
        app.stop()

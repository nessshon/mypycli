from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from mypycli.cli.parser import build_parser
from mypycli.database import DatabaseSchema
from mypycli.modules.base import Module
from mypycli.modules.interfaces.daemonic import Daemonic
from mypycli.modules.interfaces.installable import Installable
from mypycli.modules.interfaces.updatable import Updatable
from mypycli.modules.registry import ModuleRegistry


class _DaemonicModule(Daemonic):
    name = "dm"

    def on_daemon(self) -> None:
        pass


class _InstallableModule(Installable):
    name = "im"

    def on_install(self) -> None:
        pass

    def on_uninstall(self) -> None:
        pass


class _UpdatableModule(Updatable):
    name = "um"

    def on_update(self) -> None:
        pass

    @property
    def version(self) -> str:
        return "1.0.0"


class _PlainModule(Module):
    name = "pm"


def _make_app(module_classes: list[type[Module]]) -> MagicMock:
    app = MagicMock()
    app.name = "testapp"
    app.db.data = DatabaseSchema()
    app.db.is_loaded = False  # keep Module.is_enabled True pre-load
    registry = ModuleRegistry()
    for cls in module_classes:
        registry.register(cls(app))
    app.modules = registry
    return app


class TestBuildParser:
    def test_base_parser_no_subcommand(self) -> None:
        parser = build_parser(_make_app([_PlainModule]))
        assert parser.prog == "testapp"
        assert parser.parse_args([]).command is None

    def test_daemon_subcommand_only_with_daemonic(self) -> None:
        parser = build_parser(_make_app([_DaemonicModule]))
        assert parser.parse_args(["daemon"]).command == "daemon"

        with pytest.raises(SystemExit):
            build_parser(_make_app([_PlainModule])).parse_args(["daemon"])

    def test_install_and_uninstall_only_with_installable(self) -> None:
        parser = build_parser(_make_app([_InstallableModule]))
        assert parser.parse_args(["install"]).command == "install"
        assert parser.parse_args(["uninstall"]).command == "uninstall"

        with pytest.raises(SystemExit):
            build_parser(_make_app([_PlainModule])).parse_args(["install"])

    def test_update_only_with_updatable(self) -> None:
        parser = build_parser(_make_app([_UpdatableModule]))
        assert parser.parse_args(["update"]).command == "update"

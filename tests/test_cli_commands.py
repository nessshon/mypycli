from argparse import Namespace
from pathlib import Path

import pytest

from mypycli.application import Application
from mypycli.commands import cli_cmd_install, cli_cmd_uninstall, cli_cmd_update
from mypycli.modules import Installable, Updatable

calls: list[str] = []


class CoreModule(Installable, Updatable):
    name = "core"
    mandatory = True

    def __init__(self, app: Application) -> None:
        super().__init__(app)
        self._version = "aaa1111"

    @property
    def version(self) -> str:
        return self._version

    def on_install(self) -> None:
        calls.append("install core")

    def on_uninstall(self) -> None:
        calls.append("uninstall core")

    def on_update(self) -> None:
        self._version = "bbb2222"


class ExtraModule(Installable):
    name = "extra"
    mandatory = False

    def on_install(self) -> None:
        calls.append("install extra")

    def on_uninstall(self) -> None:
        calls.append("uninstall extra")


@pytest.fixture()
def app(tmp_path: Path) -> Application:
    calls.clear()
    locales = tmp_path / "locales"
    locales.mkdir()
    application = Application(
        "testapp",
        "Test App",
        False,
        work_dir=tmp_path / "work",
        logs_dir=tmp_path / "logs",
        locales_dir=locales,
        language_code="en",
    )
    application.register_module(CoreModule)
    application.register_module(ExtraModule)
    return application


def test_install_with_modules_flag(app: Application) -> None:
    cli_cmd_install(app, Namespace(modules="extra"))
    assert calls == ["install core", "install extra"]


def test_install_empty_modules_installs_mandatory_only(app: Application) -> None:
    cli_cmd_install(app, Namespace(modules=""))
    assert calls == ["install core"]


def test_install_unknown_module_exits(app: Application) -> None:
    with pytest.raises(SystemExit):
        cli_cmd_install(app, Namespace(modules="nope"))
    assert calls == []


def test_uninstall_yes_runs_in_reverse_order(app: Application) -> None:
    cli_cmd_uninstall(app, Namespace(yes=True))
    assert calls == ["uninstall extra", "uninstall core"]


def test_update_changes_version(app: Application) -> None:
    core = app.modules.get_by_class(CoreModule)
    cli_cmd_update(app, Namespace(module=None))
    assert core.version == "bbb2222"


def test_update_unknown_module_exits(app: Application) -> None:
    with pytest.raises(SystemExit):
        cli_cmd_update(app, Namespace(module="nope"))


class BrokenModule(Updatable):
    name = "broken"
    mandatory = True

    @property
    def version(self) -> str:
        return "ccc3333"

    def on_update(self) -> None:
        raise RuntimeError("boom")


def test_update_continues_past_failed_module(app: Application) -> None:
    app.register_module(BrokenModule)
    core = app.modules.get_by_class(CoreModule)
    with pytest.raises(SystemExit):
        cli_cmd_update(app, Namespace(module=None))
    assert core.version == "bbb2222"


def test_dispatch_survives_command_exception(app: Application) -> None:
    from mypycli.types import Command

    def boom(_app: Application, _args: list[str]) -> bool:
        raise ValueError("kaput")

    app.cli_parser  # noqa: B018
    app.prompt._session_running = True
    commands = app.commands
    commands.insert(0, Command("boom", boom))

    import unittest.mock

    with unittest.mock.patch.object(type(app), "commands", property(lambda _self: commands)):
        assert app.prompt._dispatch("boom") is True


def test_all_colors_render() -> None:
    from mypycli.components.console import Console
    from mypycli.types import Color

    console = Console(file=open("/dev/null", "w"))  # noqa: SIM115
    for color in Color:
        console.print("x", style=color.value)
        console.print(color("x"))
    console.note("x")

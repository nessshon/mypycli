from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from mypycli.cli.runner import run
from mypycli.database import DatabaseSchema
from mypycli.modules.interfaces.daemonic import Daemonic
from mypycli.modules.interfaces.installable import Installable
from mypycli.modules.interfaces.updatable import Updatable
from mypycli.modules.registry import ModuleRegistry

if TYPE_CHECKING:
    from _pytest.capture import CaptureFixture


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

    @property
    def version(self) -> str:
        return "0"

    def on_update(self) -> None:
        pass


def _make_app(*module_classes: type) -> MagicMock:
    app = MagicMock()
    app.name = "test"
    app.db.data = DatabaseSchema()
    app.db.is_loaded = False  # keep Module.is_enabled True pre-load
    registry = ModuleRegistry()
    for cls in module_classes:
        registry.register(cls(app))
    app.modules = registry
    app.console = MagicMock()
    return app


class TestRun:
    @patch("mypycli.cli.runner.run_console")
    def test_no_subcommand_runs_console(self, mock_rc: MagicMock) -> None:
        app = _make_app(_DaemonicModule)
        with patch("sys.argv", ["test"]):
            run(app)
        mock_rc.assert_called_once_with(app)

    @patch("mypycli.cli.runner.run_daemon")
    def test_daemon_subcommand(self, mock_rd: MagicMock) -> None:
        app = _make_app(_DaemonicModule)
        with patch("sys.argv", ["test", "daemon"]):
            run(app)
        mock_rd.assert_called_once_with(app)

    @patch("mypycli.cli.runner.is_root", return_value=True)
    @patch("mypycli.cli.runner.run_uninstall")
    def test_uninstall_subcommand(self, mock_ru: MagicMock, _mock_root: MagicMock) -> None:
        app = _make_app(_InstallableModule)
        with patch("sys.argv", ["test", "uninstall"]):
            run(app)
        mock_ru.assert_called_once_with(app)

    @patch("mypycli.cli.runner.is_root", return_value=True)
    @patch("mypycli.cli.runner.run_install")
    def test_install_subcommand(self, mock_ri: MagicMock, _mock_root: MagicMock) -> None:
        app = _make_app(_InstallableModule)
        with patch("sys.argv", ["test", "install"]):
            run(app)
        mock_ri.assert_called_once_with(app)

    @patch("mypycli.cli.runner.run_daemon")
    def test_keyboard_interrupt_translates_to_exit_130(self, mock_rd: MagicMock) -> None:
        mock_rd.side_effect = KeyboardInterrupt
        app = _make_app(_DaemonicModule)
        with patch("sys.argv", ["test", "daemon"]), pytest.raises(SystemExit) as exc:
            run(app)
        assert exc.value.code == 130


class TestRootGate:
    @pytest.mark.parametrize("command", ["install", "update", "uninstall"])
    @patch("mypycli.cli.runner.is_root", return_value=False)
    def test_commands_refused_without_root_with_sudo_hint(
        self, _mock_root: MagicMock, command: str, capsys: CaptureFixture[str]
    ) -> None:
        app = _make_app(_InstallableModule, _UpdatableModule)
        with (
            patch("mypycli.cli.runner.shutil.which", side_effect=lambda t: "/usr/bin/sudo" if t == "sudo" else None),
            patch("sys.argv", ["test", command]),
            pytest.raises(SystemExit) as exc,
        ):
            run(app)
        assert exc.value.code == 1
        err = capsys.readouterr().err
        assert f"'{command}' requires root" in err
        assert f"sudo test {command}" in err

    @patch("mypycli.cli.runner.is_root", return_value=False)
    def test_falls_back_to_su_when_no_sudo(self, _mock_root: MagicMock, capsys: CaptureFixture[str]) -> None:
        app = _make_app(_InstallableModule, _UpdatableModule)
        with (
            patch("mypycli.cli.runner.shutil.which", side_effect=lambda t: "/bin/su" if t == "su" else None),
            patch("sys.argv", ["test", "update"]),
            pytest.raises(SystemExit) as exc,
        ):
            run(app)
        assert exc.value.code == 1
        err = capsys.readouterr().err
        assert "su -c 'test update'" in err
        assert "sudo" not in err

    @patch("mypycli.cli.runner.is_root", return_value=False)
    def test_no_escalator_available_plain_hint(self, _mock_root: MagicMock, capsys: CaptureFixture[str]) -> None:
        app = _make_app(_InstallableModule)
        with (
            patch("mypycli.cli.runner.shutil.which", return_value=None),
            patch("sys.argv", ["test", "install"]),
            pytest.raises(SystemExit) as exc,
        ):
            run(app)
        assert exc.value.code == 1
        err = capsys.readouterr().err
        assert "Run as root." in err
        assert "sudo" not in err
        assert " su " not in err

    @patch("mypycli.cli.runner.is_root", return_value=True)
    @patch("mypycli.cli.runner.run_install")
    def test_root_proceeds_to_dispatch(self, mock_ri: MagicMock, _mock_root: MagicMock) -> None:
        app = _make_app(_InstallableModule)
        with patch("sys.argv", ["test", "install"]):
            run(app)
        mock_ri.assert_called_once_with(app)

    @patch("mypycli.cli.runner.is_root", return_value=False)
    @patch("mypycli.cli.runner.run_daemon")
    def test_non_root_commands_skip_gate(self, mock_rd: MagicMock, _mock_root: MagicMock) -> None:
        app = _make_app(_DaemonicModule)
        with patch("sys.argv", ["test", "daemon"]):
            run(app)
        mock_rd.assert_called_once_with(app)

    @patch("mypycli.cli.runner.is_root", return_value=False)
    @patch("mypycli.cli.runner.run_console")
    def test_console_skips_gate(self, mock_rc: MagicMock, _mock_root: MagicMock) -> None:
        app = _make_app(_DaemonicModule)
        with patch("sys.argv", ["test"]):
            run(app)
        mock_rc.assert_called_once_with(app)

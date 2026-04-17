from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar
from unittest.mock import MagicMock, patch

import pytest

from mypycli.cli.commands import (
    run_daemon,
    run_install,
    run_uninstall,
    run_update,
    select_install_modules,
)
from mypycli.database import Database, DatabaseSchema
from mypycli.modules.interfaces.daemonic import Daemonic
from mypycli.modules.interfaces.installable import Installable
from mypycli.modules.interfaces.updatable import Updatable
from mypycli.modules.registry import ModuleRegistry

if TYPE_CHECKING:
    from pathlib import Path

    from mypycli.modules.base import Module


class _DaemonicModule(Daemonic):
    name = "daemon_mod"

    def __init__(self, app: Any) -> None:
        super().__init__(app)
        self.daemon_called = False

    def on_daemon(self) -> None:
        self.daemon_called = True


class _InstallableModule(Installable):
    name = "inst_mod"
    mandatory: ClassVar[bool] = True

    def __init__(self, app: Any) -> None:
        super().__init__(app)
        self.installed = False
        self.uninstalled = False

    def on_install(self) -> None:
        self.installed = True

    def on_uninstall(self) -> None:
        self.uninstalled = True


class _OptionalInstallableModule(Installable):
    name = "opt_mod"
    mandatory: ClassVar[bool] = False

    def __init__(self, app: Any) -> None:
        super().__init__(app)
        self.installed = False

    def on_install(self) -> None:
        self.installed = True

    def on_uninstall(self) -> None:
        pass


class _RaisingInstallableModule(Installable):
    name = "boom"
    mandatory: ClassVar[bool] = True

    def on_install(self) -> None:
        raise RuntimeError("install boom")

    def on_uninstall(self) -> None:
        raise RuntimeError("uninstall boom")


class _UpdatableModule(Updatable):
    name = "upd_mod"

    def __init__(self, app: Any) -> None:
        super().__init__(app)
        self.updated = False

    def on_update(self) -> None:
        self.updated = True

    @property
    def version(self) -> str:
        return "1.0.0"


def _make_app(
    *module_classes: type[Module],
    tmp_path: Path | None = None,
    env_prefix: str | None = None,
) -> MagicMock:
    app = MagicMock()
    app.name = "test"
    app.label = "Test"
    app.env_prefix = env_prefix
    if tmp_path is not None:
        app.db = Database(DatabaseSchema, tmp_path / "test.db")
        app.start.side_effect = lambda: app.db.load(auto_create=True)
    else:
        app.db.is_loaded = False  # keep Module.is_enabled True pre-load
    registry = ModuleRegistry()
    for cls in module_classes:
        registry.register(cls(app))
    app.modules = registry
    app.console = MagicMock()
    app.worker = MagicMock()
    return app


class TestRunDaemon:
    def test_lifecycle_calls(self) -> None:
        app = _make_app(_DaemonicModule)
        app.is_running.return_value = (False, None)
        with patch.object(app, "run_forever"):
            run_daemon(app)
        mod = app.modules.by_interface(Daemonic)[0]
        assert mod.daemon_called
        app.start.assert_called_once()
        app.write_pid.assert_called_once()
        app.stop.assert_called_once()
        app.remove_pid.assert_called_once()

    def test_already_running_exits(self) -> None:
        app = _make_app(_DaemonicModule)
        app.is_running.return_value = (True, 12345)
        with pytest.raises(SystemExit) as exc:
            run_daemon(app)
        assert exc.value.code == 1
        app.start.assert_not_called()

    def test_no_daemonic_modules_exits(self) -> None:
        app = _make_app()
        app.is_running.return_value = (False, None)
        with pytest.raises(SystemExit) as exc:
            run_daemon(app)
        assert exc.value.code == 1
        app.start.assert_not_called()

    def test_requires_mandatory_installable_installed(self, tmp_path: Path) -> None:
        """Daemon refuses to start if a mandatory Installable module has no DB entry."""
        app = _make_app(_DaemonicModule, _InstallableModule, tmp_path=tmp_path)
        app.is_running.return_value = (False, None)
        with pytest.raises(SystemExit) as exc:
            run_daemon(app)
        assert exc.value.code == 1
        app.write_pid.assert_not_called()


class TestSelectInstallModules:
    def test_no_tty_returns_empty(self, tmp_path: Path) -> None:
        app = _make_app(_OptionalInstallableModule, tmp_path=tmp_path)
        app.db.load(auto_create=True)
        with patch("mypycli.cli.commands.install.sys") as mock_sys:
            mock_sys.stdin.isatty.return_value = False
            assert select_install_modules(app) == []

    def test_no_optional_returns_empty(self, tmp_path: Path) -> None:
        app = _make_app(_InstallableModule, tmp_path=tmp_path)
        app.db.load(auto_create=True)
        assert select_install_modules(app) == []

    def test_interactive_calls_multiselect(self, tmp_path: Path) -> None:
        app = _make_app(_OptionalInstallableModule, tmp_path=tmp_path)
        app.db.load(auto_create=True)
        app.console.multiselect = MagicMock(return_value=["opt_mod"])
        with patch("mypycli.cli.commands.install.sys") as mock_sys:
            mock_sys.stdin.isatty.return_value = True
            result = select_install_modules(app)
        app.console.multiselect.assert_called_once()
        assert result == ["opt_mod"]

    def test_installed_optional_hidden(self, tmp_path: Path) -> None:
        app = _make_app(_OptionalInstallableModule, tmp_path=tmp_path)
        app.db.load(auto_create=True)
        app.db.set_module_data("opt_mod", {})  # already installed
        assert select_install_modules(app) == []


class _SecondOptionalInstallableModule(Installable):
    name = "opt_two"
    mandatory: ClassVar[bool] = False

    def on_install(self) -> None:
        pass

    def on_uninstall(self) -> None:
        pass


class TestSelectInstallModulesEnv:
    def test_no_env_prefix_ignores_env_var(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """env_prefix=None → env vars are never read, multiselect still drives selection."""
        app = _make_app(_OptionalInstallableModule, tmp_path=tmp_path, env_prefix=None)
        app.db.load(auto_create=True)
        monkeypatch.setenv("TEST_MODULES", "opt_mod")
        app.console.multiselect = MagicMock(return_value=[])
        with patch("mypycli.cli.commands.install.sys") as mock_sys:
            mock_sys.stdin.isatty.return_value = True
            result = select_install_modules(app)
        app.console.multiselect.assert_called_once()
        assert result == []

    def test_non_tty_no_env_returns_empty(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        app = _make_app(_OptionalInstallableModule, tmp_path=tmp_path, env_prefix="TEST")
        app.db.load(auto_create=True)
        monkeypatch.delenv("TEST_MODULES", raising=False)
        with patch("mypycli.cli.commands.install.sys") as mock_sys:
            mock_sys.stdin.isatty.return_value = False
            assert select_install_modules(app) == []

    def test_non_tty_empty_env_returns_empty(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        app = _make_app(_OptionalInstallableModule, tmp_path=tmp_path, env_prefix="TEST")
        app.db.load(auto_create=True)
        monkeypatch.setenv("TEST_MODULES", "")
        with patch("mypycli.cli.commands.install.sys") as mock_sys:
            mock_sys.stdin.isatty.return_value = False
            assert select_install_modules(app) == []

    def test_non_tty_env_returns_listed(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        app = _make_app(_OptionalInstallableModule, tmp_path=tmp_path, env_prefix="TEST")
        app.db.load(auto_create=True)
        monkeypatch.setenv("TEST_MODULES", "opt_mod")
        with patch("mypycli.cli.commands.install.sys") as mock_sys:
            mock_sys.stdin.isatty.return_value = False
            assert select_install_modules(app) == ["opt_mod"]

    def test_tty_env_bypasses_multiselect(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        app = _make_app(_OptionalInstallableModule, tmp_path=tmp_path, env_prefix="TEST")
        app.db.load(auto_create=True)
        app.console.multiselect = MagicMock(return_value=[])
        monkeypatch.setenv("TEST_MODULES", "opt_mod")
        with patch("mypycli.cli.commands.install.sys") as mock_sys:
            mock_sys.stdin.isatty.return_value = True
            result = select_install_modules(app)
        app.console.multiselect.assert_not_called()
        assert result == ["opt_mod"]

    def test_tty_empty_env_still_prompts(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        app = _make_app(_OptionalInstallableModule, tmp_path=tmp_path, env_prefix="TEST")
        app.db.load(auto_create=True)
        app.console.multiselect = MagicMock(return_value=["opt_mod"])
        monkeypatch.setenv("TEST_MODULES", "   ")
        with patch("mypycli.cli.commands.install.sys") as mock_sys:
            mock_sys.stdin.isatty.return_value = True
            result = select_install_modules(app)
        app.console.multiselect.assert_called_once()
        assert result == ["opt_mod"]

    def test_unknown_name_raises_runtime_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        app = _make_app(
            _OptionalInstallableModule,
            _SecondOptionalInstallableModule,
            tmp_path=tmp_path,
            env_prefix="TEST",
        )
        app.db.load(auto_create=True)
        monkeypatch.setenv("TEST_MODULES", "opt_mod,ghost,phantom")
        with pytest.raises(RuntimeError) as exc:
            select_install_modules(app)
        msg = str(exc.value)
        assert "TEST_MODULES" in msg
        assert "ghost" in msg and "phantom" in msg
        assert "opt_mod" in msg and "opt_two" in msg  # available optional list

    def test_unknown_when_no_optional_available(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        app = _make_app(_InstallableModule, tmp_path=tmp_path, env_prefix="TEST")
        app.db.load(auto_create=True)
        monkeypatch.setenv("TEST_MODULES", "ghost")
        with pytest.raises(RuntimeError, match=r"\(none\)"):
            select_install_modules(app)

    def test_mandatory_name_silently_skipped(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        app = _make_app(
            _InstallableModule,
            _OptionalInstallableModule,
            tmp_path=tmp_path,
            env_prefix="TEST",
        )
        app.db.load(auto_create=True)
        monkeypatch.setenv("TEST_MODULES", "inst_mod,opt_mod")
        with patch("mypycli.cli.commands.install.sys") as mock_sys:
            mock_sys.stdin.isatty.return_value = False
            assert select_install_modules(app) == ["opt_mod"]

    def test_env_only_mandatory_yields_empty_result(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        app = _make_app(_InstallableModule, tmp_path=tmp_path, env_prefix="TEST")
        app.db.load(auto_create=True)
        monkeypatch.setenv("TEST_MODULES", "inst_mod")
        with patch("mypycli.cli.commands.install.sys") as mock_sys:
            mock_sys.stdin.isatty.return_value = False
            assert select_install_modules(app) == []

    def test_installed_optional_silently_skipped(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        app = _make_app(
            _OptionalInstallableModule,
            _SecondOptionalInstallableModule,
            tmp_path=tmp_path,
            env_prefix="TEST",
        )
        app.db.load(auto_create=True)
        app.db.set_module_data("opt_mod", {})  # already installed
        monkeypatch.setenv("TEST_MODULES", "opt_mod,opt_two")
        with patch("mypycli.cli.commands.install.sys") as mock_sys:
            mock_sys.stdin.isatty.return_value = False
            assert select_install_modules(app) == ["opt_two"]

    def test_csv_whitespace_and_empties_tolerated(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        app = _make_app(
            _OptionalInstallableModule,
            _SecondOptionalInstallableModule,
            tmp_path=tmp_path,
            env_prefix="TEST",
        )
        app.db.load(auto_create=True)
        monkeypatch.setenv("TEST_MODULES", " opt_mod , ,opt_two ,")
        with patch("mypycli.cli.commands.install.sys") as mock_sys:
            mock_sys.stdin.isatty.return_value = False
            assert select_install_modules(app) == ["opt_mod", "opt_two"]

    def test_env_var_name_uses_prefix(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """select_install_modules reads {prefix}_MODULES, not any fixed name."""
        app = _make_app(_OptionalInstallableModule, tmp_path=tmp_path, env_prefix="CUSTOM")
        app.db.load(auto_create=True)
        monkeypatch.setenv("TEST_MODULES", "opt_mod")  # wrong prefix, must be ignored
        monkeypatch.setenv("CUSTOM_MODULES", "opt_mod")
        with patch("mypycli.cli.commands.install.sys") as mock_sys:
            mock_sys.stdin.isatty.return_value = False
            assert select_install_modules(app) == ["opt_mod"]


class TestRunInstall:
    def test_mandatory_always_installed(self, tmp_path: Path) -> None:
        app = _make_app(_InstallableModule, tmp_path=tmp_path)
        run_install(app, selected=[])
        assert app.modules.get("inst_mod").installed is True

    def test_optional_skipped_when_not_selected(self, tmp_path: Path) -> None:
        app = _make_app(_OptionalInstallableModule, tmp_path=tmp_path)
        run_install(app, selected=[])
        assert app.modules.get("opt_mod").installed is False

    def test_optional_installed_when_selected(self, tmp_path: Path) -> None:
        app = _make_app(_OptionalInstallableModule, tmp_path=tmp_path)
        run_install(app, selected=["opt_mod"])
        assert app.modules.get("opt_mod").installed is True

    def test_stop_on_first_failure(self, tmp_path: Path) -> None:
        app = _make_app(_RaisingInstallableModule, _InstallableModule, tmp_path=tmp_path)
        with pytest.raises(SystemExit) as exc:
            run_install(app, selected=[])
        assert exc.value.code == 1
        assert app.modules.get("inst_mod").installed is False

    def test_preserves_existing_db_extras(self, tmp_path: Path) -> None:
        (tmp_path / "test.db").write_text('{"my_extra": "keep me"}')
        app = _make_app(_InstallableModule, tmp_path=tmp_path)
        run_install(app, selected=[])
        assert app.db.get_extra("my_extra") == "keep me"


class TestRunUninstall:
    def test_calls_on_uninstall(self, tmp_path: Path) -> None:
        app = _make_app(_InstallableModule, tmp_path=tmp_path)
        app.db.load(auto_create=True)
        app.db.set_module_data("inst_mod", {})
        app.console.confirm = MagicMock(return_value=True)
        with patch("mypycli.cli.commands.uninstall.sys") as mock_sys:
            mock_sys.stdin.isatty.return_value = True
            run_uninstall(app)
        assert app.modules.get("inst_mod").uninstalled

    def test_no_tty_exits(self, tmp_path: Path) -> None:
        app = _make_app(_InstallableModule, tmp_path=tmp_path)
        with patch("mypycli.cli.commands.uninstall.sys") as mock_sys:
            mock_sys.stdin.isatty.return_value = False
            with pytest.raises(SystemExit) as exc:
                run_uninstall(app)
        assert exc.value.code == 1
        assert not app.modules.get("inst_mod").uninstalled

    def test_tty_confirm_no_aborts(self, tmp_path: Path) -> None:
        app = _make_app(_InstallableModule, tmp_path=tmp_path)
        app.console.confirm = MagicMock(return_value=False)
        with patch("mypycli.cli.commands.uninstall.sys") as mock_sys:
            mock_sys.stdin.isatty.return_value = True
            run_uninstall(app)
        assert not app.modules.get("inst_mod").uninstalled

    def test_failure_in_one_module_continues_others(self, tmp_path: Path) -> None:
        app = _make_app(_InstallableModule, _RaisingInstallableModule, tmp_path=tmp_path)
        app.db.load(auto_create=True)
        app.db.set_module_data("inst_mod", {})
        app.db.set_module_data("boom", {})
        app.console.confirm = MagicMock(return_value=True)
        with patch("mypycli.cli.commands.uninstall.sys") as mock_sys:
            mock_sys.stdin.isatty.return_value = True
            with pytest.raises(SystemExit) as exc:
                run_uninstall(app)
        assert exc.value.code == 1
        assert app.modules.get("inst_mod").uninstalled


class TestRunUpdate:
    def test_runs_all(self, tmp_path: Path) -> None:
        app = _make_app(_UpdatableModule, tmp_path=tmp_path)
        app.db.load(auto_create=True)
        app.db.set_module_data("upd_mod", {})
        run_update(app)
        assert app.modules.get("upd_mod").updated

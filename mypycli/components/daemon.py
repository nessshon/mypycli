from __future__ import annotations

import os
import signal
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from mypycli.modules import Daemonic

if TYPE_CHECKING:
    from mypycli.application import Application


class Daemon:
    def __init__(self, app: Application) -> None:
        self._app = app
        self._stop_event = threading.Event()
        self.pid_path = Path(f"{app.work_dir}/{app.name}.pid")

    def write_pid(self) -> None:
        self.pid_path.write_text(str(os.getpid()), encoding="utf-8")

    def read_pid(self) -> int | None:
        try:
            return int(self.pid_path.read_text().strip())
        except (FileNotFoundError, ValueError, OSError):
            return None

    def remove_pid(self) -> None:
        self.pid_path.unlink(missing_ok=True)

    def is_running(self) -> bool:
        pid = self.read_pid()
        if pid is None:
            return False
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    def run(self) -> None:
        if self.is_running():
            raise RuntimeError("Daemon is already running")
        if not self._app.modules.get_by_interface(Daemonic, enabled_only=False):
            raise RuntimeError("No Daemonic modules registered")

        self._install_signal_handlers()
        self._stop_event.clear()
        self.write_pid()
        try:
            for daemonic in self._app.modules.get_by_interface(Daemonic):
                daemonic.on_daemon()
            self._stop_event.wait()
        finally:
            self.remove_pid()

    def stop(self) -> None:
        if self.is_running():
            self._stop_event.set()

    def _install_signal_handlers(self) -> None:
        def handler(_signum: int, _frame: object) -> None:
            self._stop_event.set()

        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, handler)

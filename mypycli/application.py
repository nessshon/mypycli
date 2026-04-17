from __future__ import annotations

import contextlib
import logging
import os
import signal
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Generic, TypeVar

from mypycli.__meta__ import __title__
from mypycli.console.console import Console
from mypycli.database import Database, DatabaseSchema
from mypycli.i18n import internal as _i18n_internal
from mypycli.i18n.detect import parse_lang_env
from mypycli.logger import add_file_handler, setup_logger
from mypycli.modules.interfaces.installable import Installable
from mypycli.modules.registry import ModuleRegistry, build_modules
from mypycli.utils.daemon import is_alive, read_pid
from mypycli.utils.worker import Worker

if TYPE_CHECKING:
    from mypycli.i18n.translator import Translator
    from mypycli.modules.base import Module

T = TypeVar("T", bound=DatabaseSchema)


class Application(Generic[T]):
    """Application facade wiring database, worker, console, logger and modules.

    :param db_schema: DatabaseSchema subclass used to type and validate the on-disk JSON store.
    :param work_dir: Directory for PID, log and database files; created if missing.
    :param name: App identifier; lowercased and used as the stem for ``<name>.pid``,
        ``<name>.log`` and ``<name>.db``.
    :param label: Human-readable name for console display; defaults to ``name``.
    :param modules: Module classes to instantiate and register on construction.
    :param welcome: Console welcome banner; ``None`` uses the default, ``""`` disables it.
    :param goodbye: Console goodbye banner; ``None`` uses the default, ``""`` disables it.
    :param env_prefix: Prefix for environment variables read by the framework (for example
        ``<PREFIX>_MODULES`` in non-interactive ``install``). ``None`` disables all env lookups.
    :param translator: ``Translator`` instance bound to this application; drives
        all user-facing translations.
    """

    def __init__(
        self,
        db_schema: type[T],
        work_dir: str | Path,
        translator: Translator,
        *,
        name: str = __title__,
        label: str | None = None,
        modules: list[type[Module]] | None = None,
        welcome: str | None = None,
        goodbye: str | None = None,
        env_prefix: str | None = None,
    ) -> None:
        self.name = name.lower()
        self.label = label or name
        self.env_prefix = env_prefix
        self.translator = translator

        self._work_dir = Path(work_dir).resolve()
        self._work_dir.mkdir(parents=True, exist_ok=True)

        self.logger: logging.Logger = setup_logger(self.name, level=logging.INFO)
        self.console: Console = Console(app=self, welcome=welcome, goodbye=goodbye)
        self.db: Database[T] = Database(
            db_schema,
            self._work_dir / f"{self.name}.db",
            logger=self.logger,
        )
        self.modules: ModuleRegistry = ModuleRegistry()
        self.worker: Worker = Worker(logger=self.logger)

        if modules:
            build_modules(self, modules)

        self._shutdown_event = threading.Event()

    @property
    def work_dir(self) -> Path:
        """Return the application's working directory."""
        return self._work_dir

    @property
    def pid_path(self) -> Path:
        """Return the path to the PID file."""
        return self._work_dir / f"{self.name}.pid"

    @property
    def log_path(self) -> Path:
        """Return the path to the log file."""
        return self._work_dir / f"{self.name}.log"

    def start(self) -> None:
        """Load the database, resolve language, and attach the log file.

        The log always goes to ``<work_dir>/<name>.log`` — stdout is reserved
        for the ``Console`` UX layer and is never written to by the logger.
        """
        self.db.load(auto_create=True)
        self._register_non_installables()
        self._resolve_and_apply_language()
        _i18n_internal.bind(self.translator)
        self.logger.setLevel(logging.DEBUG if self.db.debug else logging.INFO)
        self.enable_file_logging()
        self.logger.debug(f"Application '{self.name}' started (pid={os.getpid()})")

    def _resolve_and_apply_language(self) -> None:
        """Resolve effective language from db/env/fallback and apply to the translator."""
        available = self.translator.available_languages()
        if not available:
            raise RuntimeError(f"No language catalogs in {self.translator.locales_dir}")

        current = self.db.language
        if current and current in available:
            self.translator.set_language(current)
            return

        detected = parse_lang_env(os.environ.get("LANG", ""))
        if detected and detected in available:
            self.db.language = detected
            self.translator.set_language(detected)
            return

        chosen = "en" if "en" in available else sorted(available)[0]
        self.db.language = chosen
        self.translator.set_language(chosen)

    def _register_non_installables(self) -> None:
        """Write an empty DB entry for every non-Installable module that has none yet.

        Non-Installable modules have no install phase; their presence in the registry
        means they are enabled. Installable modules get their key via ``on_install``.
        """
        installed = set(self.db.installed_modules())
        for module in self.modules.all(enabled_only=False):
            if not isinstance(module, Installable) and module.name not in installed:
                self.db.set_module_data(module.name, {})

    def stop(self) -> None:
        """Stop the worker, close module event loops and log shutdown."""
        self.logger.debug(f"Application '{self.name}' stopping")
        self.worker.stop()
        self.worker.wait(timeout=10)
        for module in self.modules.all(enabled_only=False):
            module.close_async_loop()
        self.logger.debug(f"Application '{self.name}' stopped")

    def write_pid(self) -> None:
        """Write the current process ID to the PID file."""
        self.pid_path.write_text(str(os.getpid()), encoding="utf-8")

    def remove_pid(self) -> None:
        """Remove the PID file if present; no-op otherwise."""
        self.pid_path.unlink(missing_ok=True)

    def is_running(self) -> tuple[bool, int | None]:
        """Check whether a daemon process is alive based on the PID file.

        :returns: ``(True, pid)`` when the process exists, ``(False, pid)`` for
            a stale PID file, ``(False, None)`` when no PID file is present.
        """
        pid = read_pid(self.pid_path)
        if pid is None:
            return False, None
        alive = is_alive(pid)
        # alive is None means EPERM — process exists but belongs to another user;
        # conservative: treat as running so we don't start a second daemon.
        if alive is True or alive is None:
            return True, pid
        return False, pid

    def enable_file_logging(self) -> None:
        """Attach the rotating log file handler to the application logger (idempotent).

        Invoked from ``start()``; the only logger attachment the framework owns.
        Stdout stays reserved for the ``Console`` UX channel.
        """
        from logging.handlers import RotatingFileHandler

        if any(isinstance(h, RotatingFileHandler) for h in self.logger.handlers):
            return
        add_file_handler(self.logger, self.log_path)

    def run_forever(self) -> None:
        """Block until SIGTERM, SIGINT or ``KeyboardInterrupt`` triggers shutdown."""
        self._setup_signals()
        with contextlib.suppress(KeyboardInterrupt):
            self._shutdown_event.wait()

    def run(self) -> None:
        """Parse CLI arguments and dispatch to the matching mode (entry point)."""
        from mypycli.cli.runner import run

        run(self)

    def _setup_signals(self) -> None:
        """Install SIGTERM and SIGINT handlers that trigger graceful shutdown."""
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, self._handle_signal)

    def _handle_signal(self, signum: int, _frame: object) -> None:
        """Set the shutdown event so ``run_forever`` unblocks.

        :param signum: Signal number received.
        :param _frame: Current stack frame; unused.
        """
        self.logger.debug(f"Received signal {signal.Signals(signum).name}")
        self._shutdown_event.set()

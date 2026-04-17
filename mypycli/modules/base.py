from __future__ import annotations

import asyncio
import inspect
import logging
import re
import threading
from typing import TYPE_CHECKING, Any, ClassVar, TypeVar

from mypycli.utils.worker import CycleTask, Task

_NAME_RE = re.compile(r"[a-z0-9][a-z0-9_-]*")

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from mypycli.application import Application
    from mypycli.database import DatabaseSchema

_R = TypeVar("_R")


class Module:
    """Base class for all application modules.

    :cvar name: Unique module identifier; required non-empty string on concrete subclasses.
    :cvar label: Human-readable label; falls back to ``name`` when empty.
    :cvar mandatory: When ``True``, framework guarantees the module is always enabled
        (auto-installs Installable mandatories, writes an empty DB key for the rest).
    :cvar db_schema: Optional DatabaseSchema subclass enabling typed per-module storage via ``self.db``.
    :cvar __abstract__: When ``True`` on a subclass itself (not inherited), the framework skips
        ``name`` validation. Use for intermediate/mixin classes that implement interface methods
        but are not concrete modules. Follows the SQLAlchemy ``__abstract__`` convention.
    """

    name: ClassVar[str]
    label: ClassVar[str] = ""
    mandatory: ClassVar[bool] = False
    db_schema: ClassVar[type[DatabaseSchema] | None] = None

    app: Application[Any]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if inspect.isabstract(cls):
            return
        if cls.__dict__.get("__abstract__", False):
            return
        name = getattr(cls, "name", None)
        if not name or not isinstance(name, str):
            raise TypeError(f"{cls.__name__} must define a non-empty 'name' class variable")
        if not _NAME_RE.fullmatch(name):
            raise TypeError(
                f"{cls.__name__}.name must match [a-z0-9][a-z0-9_-]* (got {name!r}); "
                f"use 'label' for display names with casing or spaces"
            )

    def __init__(self, app: Application[Any]) -> None:
        self.app = app

        self._async_loop: asyncio.AbstractEventLoop | None = None
        self._async_thread: threading.Thread | None = None

        self._logger = logging.getLogger(f"{app.name}.{self.name}")

    @property
    def db(self) -> Any:
        """Return the module's typed DB section, freshly read from disk.

        Each access materializes a new Pydantic instance from ``db.modules[self.name]``
        and wires auto-save callbacks; field assignment persists immediately. No
        caching — readers always see writes from other processes (daemon ↔ REPL).

        :raises TypeError: Module declared no ``db_schema``.
        :raises RuntimeError: Accessed before ``Database.load()`` succeeded.
        """
        from mypycli.database.schema import _wire_patch

        if self.db_schema is None:
            raise TypeError(f"Module '{self.name}' has no db_schema")
        if not self.app.db.is_loaded:
            raise RuntimeError(
                f"Module '{self.name}' accessed '.db' before Database.load(); call app.start() or app.db.load() first"
            )
        raw = self.app.db.get_module_data(self.name)
        instance = self.db_schema.model_validate(raw)
        _wire_patch(instance, self._on_db_patch)
        return instance

    @property
    def logger(self) -> logging.Logger:
        """Child logger named ``<app.name>.<module.name>`` (cached at ``__init__``)."""
        return self._logger

    @property
    def display_name(self) -> str:
        """Return ``label`` when set, otherwise ``name``."""
        return self.label or self.name

    @property
    def is_enabled(self) -> bool:
        """Whether the module participates in runtime lookups (daemon, console, status, ...).

        Enabled iff ``self.name`` is present in ``db.modules`` (written by install
        for Installable modules, or by ``Application.start`` for mandatory ones).
        Returns ``True`` before the database is loaded so parser construction sees
        all modules; override for custom activation logic.
        """
        if not self.app.db.is_loaded:
            return True
        return self.name in self.app.db.installed_modules()

    def run_async(self, coro: Coroutine[Any, Any, _R]) -> _R:
        """Run an async coroutine on the module's background loop and return its result."""
        if self._async_loop is None:
            self.open_async_loop()
        loop = self._async_loop
        if loop is None:
            raise RuntimeError("Failed to create async event loop")
        return asyncio.run_coroutine_threadsafe(coro, loop).result()

    def open_async_loop(self) -> None:
        """Start the module's background asyncio loop in a daemon thread (idempotent)."""
        if self._async_loop is None or self._async_loop.is_closed():
            self._async_loop = asyncio.new_event_loop()
            self._async_thread = threading.Thread(
                target=self._start_event_loop,
                args=(self._async_loop,),
                daemon=True,
            )
            self._async_thread.start()

    def close_async_loop(self) -> None:
        """Stop and join the background asyncio loop (idempotent)."""
        if self._async_loop is not None and not self._async_loop.is_closed():
            self._async_loop.call_soon_threadsafe(self._async_loop.stop)
        if self._async_thread is not None:
            self._async_thread.join(timeout=5)
            self._async_thread = None
        self._async_loop = None

    def run_task(self, func: Callable[..., Any], *, suffix: str | None = None) -> Task:
        """Register ``func`` as a one-shot background Task on the app worker and start it.

        The task name is ``<module.name>.<suffix or func.__name__>`` so logs and
        ``threadName`` are clearly module-attributed. Exceptions are routed to the
        module's logger.

        :param func: Callable to execute once in a daemon thread.
        :param suffix: Override the auto-derived task-name suffix.
        :returns: The started Task.
        """
        name = f"{self.name}.{suffix or func.__name__}"
        return self.app.worker.add(Task(func, self._logger, name=name))

    def run_cycle(
        self,
        func: Callable[..., Any],
        *,
        seconds: float,
        suffix: str | None = None,
    ) -> CycleTask:
        """Register ``func`` as a periodic CycleTask on the app worker and start it.

        Same naming and logging rules as ``run_task``; the cycle wait is
        interruptible via the worker's shared stop signal.

        :param func: Callable invoked on every cycle.
        :param seconds: Delay between successive invocations.
        :param suffix: Override the auto-derived task-name suffix.
        :returns: The started CycleTask.
        """
        name = f"{self.name}.{suffix or func.__name__}"
        task = CycleTask(func, self._logger, seconds=seconds, name=name)
        self.app.worker.add(task)
        return task

    def _on_db_patch(self, field: str, value: Any) -> None:
        self.app.db.patch_module_data(self.name, {field: value})

    @staticmethod
    def _start_event_loop(loop: asyncio.AbstractEventLoop) -> None:
        asyncio.set_event_loop(loop)
        loop.run_forever()

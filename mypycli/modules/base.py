from __future__ import annotations

import asyncio
import inspect
import logging
import re
import threading
from abc import ABC
from typing import TYPE_CHECKING, Any, ClassVar, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from mypycli.application import Application
    from mypycli.components.worker import CycleTask, Task

_AsyncR = TypeVar("_AsyncR")
_NAME_RE = re.compile(r"[a-z0-9][a-z0-9_-]*")


class Module(ABC):
    name: ClassVar[str]
    label: ClassVar[str] = ""
    mandatory: ClassVar[bool] = False

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if inspect.isabstract(cls):
            return
        name = getattr(cls, "name", None)
        if not name or not isinstance(name, str):
            raise TypeError(f"{cls.__name__} must define a non-empty 'name' class variable")
        if not _NAME_RE.fullmatch(name):
            raise TypeError(
                f"{cls.__name__}.name must match [a-z0-9][a-z0-9_-]* (got {name!r}); "
                f"use 'label' for display names with casing or spaces"
            )

    def __init__(self, app: Application) -> None:
        self.app = app
        self.logger = logging.getLogger(f"{app.name}.{self.name}")

        self._async_loop: asyncio.AbstractEventLoop | None = None
        self._async_thread: threading.Thread | None = None

    @property
    def is_enabled(self) -> bool:
        return self.mandatory

    @property
    def display_name(self) -> str:
        return self.label or self.name

    def run_task(self, func: Callable[[], Any], *, name: str | None = None) -> Task:
        return self.app.worker.run(func, name=f"{self.name}.{name or func.__name__}")

    def run_cycle(self, func: Callable[[], Any], *, seconds: float, name: str | None = None) -> CycleTask:
        return self.app.worker.run_cycle(func, seconds=seconds, name=f"{self.name}.{name or func.__name__}")

    def run_async(self, coro: Coroutine[Any, Any, _AsyncR]) -> _AsyncR:
        if self._async_loop is None:
            self.open_async_loop()
        loop = self._async_loop
        if loop is None:
            raise RuntimeError("Failed to create async event loop")
        return asyncio.run_coroutine_threadsafe(coro, loop).result()

    def open_async_loop(self) -> None:
        if self._async_loop is None or self._async_loop.is_closed():
            self._async_loop = asyncio.new_event_loop()
            self._async_thread = threading.Thread(
                target=self._start_event_loop,
                args=(self._async_loop,),
                daemon=True,
            )
            self._async_thread.start()

    def close_async_loop(self) -> None:
        if self._async_loop is not None and not self._async_loop.is_closed():
            self._async_loop.call_soon_threadsafe(self._async_loop.stop)
        if self._async_thread is not None:
            self._async_thread.join(timeout=5)
            self._async_thread = None
        if self._async_loop is not None and not self._async_loop.is_running():
            self._async_loop.close()
        self._async_loop = None

    @staticmethod
    def _start_event_loop(loop: asyncio.AbstractEventLoop) -> None:
        asyncio.set_event_loop(loop)
        loop.run_forever()

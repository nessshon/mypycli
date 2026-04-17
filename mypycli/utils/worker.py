from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import logging
    from collections.abc import Callable


class Task:
    """Background job wrapping a callable in a daemon thread with cooperative cancellation.

    :param func: Callable executed once when the thread starts.
    :param logger: Logger used to report unhandled exceptions from ``func``.
    :param name: Human-readable task name; defaults to ``func.__name__``.
    """

    def __init__(
        self,
        func: Callable[..., Any],
        logger: logging.Logger,
        *,
        name: str | None = None,
    ) -> None:
        self.name = name or func.__name__
        self._func = func
        self._logger = logger
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def is_running(self) -> bool:
        """Whether the underlying thread has been started and has not yet finished."""
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        """Clear the stop signal and launch ``func`` in a fresh daemon thread."""
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name=self.name, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Set the internal stop event; the callable must cooperate to actually exit early."""
        self._stop_event.set()

    def wait(self, timeout: float | None = None) -> None:
        """Join the task thread, blocking until it exits.

        No-op if the task was never started.

        :param timeout: Maximum seconds to wait; ``None`` waits indefinitely.
        """
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    def _run(self) -> None:
        try:
            self._func()
        except Exception:
            self._logger.exception(f"Task '{self.name}' failed")


class CycleTask(Task):
    """Task that invokes ``func`` on a fixed interval until ``stop()`` is called.

    Exceptions raised by ``func`` are logged and the loop continues;
    the inter-cycle wait is interruptible via the stop event.

    :param func: Callable executed every cycle.
    :param logger: Logger used to report exceptions from each cycle.
    :param seconds: Delay between the end of one cycle and the start of the next.
    :param name: Human-readable task name; defaults to ``func.__name__``.
    """

    def __init__(
        self,
        func: Callable[..., Any],
        logger: logging.Logger,
        *,
        seconds: float,
        name: str | None = None,
    ) -> None:
        super().__init__(func, logger, name=name)
        self._seconds = seconds

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._func()
            except Exception:
                self._logger.exception(f"Cycle task '{self.name}' failed, continuing")
            self._stop_event.wait(self._seconds)


class Worker:
    """Thread-safe registry that owns a set of named background tasks.

    :param logger: Logger passed to tasks created through ``run`` and ``cycle``.
    """

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger
        self._tasks: dict[str, Task] = {}
        self._lock = threading.Lock()

    @property
    def active(self) -> list[Task]:
        """Snapshot of registered tasks whose threads are still alive."""
        with self._lock:
            return [t for t in self._tasks.values() if t.is_running]

    def add(self, task: Task) -> Task:
        """Register ``task`` under its name and start its thread immediately.

        :param task: Task to register and start.
        :returns: The same task, for call chaining.
        :raises ValueError: If another task with the same name is already registered.
        """
        with self._lock:
            if task.name in self._tasks:
                raise ValueError(f"Duplicate task name: {task.name!r}")
            self._tasks[task.name] = task
        task.start()
        return task

    def run(self, func: Callable[..., Any], *, name: str | None = None) -> Task:
        """Wrap ``func`` in a one-shot Task, register it, and start it.

        :param func: Callable executed once by the task thread.
        :param name: Task name; defaults to ``func.__name__``.
        :returns: The started Task.
        """
        return self.add(Task(func, self._logger, name=name))

    def cycle(self, func: Callable[..., Any], *, seconds: float, name: str | None = None) -> CycleTask:
        """Wrap ``func`` in a CycleTask that runs every ``seconds``, register it, and start it.

        :param func: Callable invoked on each cycle.
        :param seconds: Delay between successive invocations.
        :param name: Task name; defaults to ``func.__name__``.
        :returns: The started CycleTask.
        """
        task = CycleTask(func, self._logger, seconds=seconds, name=name)
        self.add(task)
        return task

    def get(self, name: str) -> Task | None:
        """Return the registered task with the given name, or ``None`` if none matches.

        :param name: Task name to look up.
        """
        with self._lock:
            return self._tasks.get(name)

    def remove(self, name: str) -> None:
        """Unregister the named task and signal it to stop; no-op if the name is unknown.

        :param name: Name of the task to remove.
        """
        with self._lock:
            task = self._tasks.pop(name, None)
        if task:
            task.stop()

    def stop(self) -> None:
        """Signal every registered task to stop; does not wait for them to finish."""
        with self._lock:
            tasks = list(self._tasks.values())
        for task in tasks:
            task.stop()

    def wait(self, timeout: float | None = None) -> None:
        """Join every registered task sequentially.

        :param timeout: Total budget in seconds shared across all joins
            (divided by remaining wall time per task); ``None`` waits indefinitely.
        """
        with self._lock:
            tasks = list(self._tasks.values())
        if timeout is None:
            for task in tasks:
                task.wait()
        else:
            deadline = time.monotonic() + timeout
            for task in tasks:
                remaining = max(0.0, deadline - time.monotonic())
                task.wait(timeout=remaining)

import logging
import threading
from collections.abc import Callable
from typing import Any


class Task:
    def __init__(
        self,
        func: Callable[..., Any],
        *,
        name: str,
        logger: logging.Logger,
    ) -> None:
        self.func = func
        self.name = name
        self.logger = logger

        self._thread: threading.Thread | None = None

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if not self.is_running():
            self._thread = threading.Thread(
                target=self._run,
                name=self.name,
                daemon=True,
            )
            self._thread.start()

    def join(self, timeout: float | None = None) -> None:
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    def _run(self) -> None:
        try:
            self.func()
        except Exception:
            self.logger.exception("task failed")


class CycleTask(Task):
    def __init__(
        self,
        func: Callable[..., Any],
        *,
        name: str,
        seconds: float,
        logger: logging.Logger,
    ) -> None:
        super().__init__(func, name=name, logger=logger)

        self.seconds = seconds
        self._stop_event = threading.Event()

    def start(self) -> None:
        self._stop_event.clear()
        super().start()

    def stop(self) -> None:
        self._stop_event.set()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.func()
            except Exception:
                self.logger.exception(
                    "cycle task failed, retrying in %s seconds",
                    self.seconds,
                )
            self._stop_event.wait(self.seconds)


class Worker:
    def __init__(self, name: str) -> None:
        self.name = name
        self._lock = threading.Lock()
        self._tasks: dict[str, Task] = {}

    def run(
        self,
        func: Callable[..., Any],
        *,
        name: str | None = None,
    ) -> Task:
        task_name = name or func.__name__
        task = Task(
            func=func,
            name=task_name,
            logger=logging.getLogger(f"{self.name}.{task_name}"),
        )
        self._register(task)
        return task

    def run_cycle(
        self,
        func: Callable[..., Any],
        *,
        name: str | None = None,
        seconds: float,
    ) -> CycleTask:
        task_name = name or func.__name__
        task = CycleTask(
            func=func,
            seconds=seconds,
            name=task_name,
            logger=logging.getLogger(f"{self.name}.{task_name}"),
        )
        self._register(task)
        return task

    def stop_all(self, timeout: float = 5.0) -> None:
        with self._lock:
            tasks = list(self._tasks.values())
            self._tasks.clear()
        for task in tasks:
            if isinstance(task, CycleTask):
                task.stop()
        for task in tasks:
            task.join(timeout=timeout)

    def _register(self, task: Task) -> None:
        with self._lock:
            if task.name in self._tasks:
                raise ValueError(
                    f"Task {task.name} already registered",
                )
            self._tasks[task.name] = task
            task.start()

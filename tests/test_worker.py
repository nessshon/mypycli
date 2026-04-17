from __future__ import annotations

import logging
import threading
import time

import pytest

from mypycli.utils.worker import CycleTask, Task, Worker

_LOGGER = logging.getLogger("test.worker")


class TestTask:
    def test_runs_and_finishes(self) -> None:
        result: list[int] = []
        task = Task(lambda: result.append(1), _LOGGER, name="t")
        task.start()
        task.wait(timeout=2)
        assert result == [1]
        assert not task.is_running

    def test_exception_is_logged_not_raised(self, caplog: pytest.LogCaptureFixture) -> None:
        def failing() -> None:
            raise RuntimeError("boom")

        task = Task(failing, _LOGGER, name="fail")
        with caplog.at_level(logging.ERROR, logger="test.worker"):
            task.start()
            task.wait(timeout=2)
        assert not task.is_running
        assert "boom" in caplog.text

    def test_name_defaults_to_func_name(self) -> None:
        def my_func() -> None:
            pass

        assert Task(my_func, _LOGGER).name == "my_func"


class TestCycleTask:
    def test_repeats_until_stopped(self) -> None:
        counter = [0]
        task = CycleTask(lambda: counter.__setitem__(0, counter[0] + 1), _LOGGER, seconds=0.02, name="cycle")
        task.start()
        time.sleep(0.15)
        task.stop()
        task.wait(timeout=2)
        assert counter[0] >= 3

    def test_stop_breaks_cycle(self) -> None:
        counter = [0]
        task = CycleTask(lambda: counter.__setitem__(0, counter[0] + 1), _LOGGER, seconds=0.01, name="stoppable")
        task.start()
        time.sleep(0.05)
        task.stop()
        task.wait(timeout=2)
        snapshot = counter[0]
        time.sleep(0.05)
        assert counter[0] == snapshot

    def test_exception_does_not_kill_cycle(self) -> None:
        calls = [0]

        def flaky() -> None:
            calls[0] += 1
            if calls[0] == 1:
                raise ValueError("first call fails")

        task = CycleTask(flaky, _LOGGER, seconds=0.02, name="flaky")
        task.start()
        time.sleep(0.1)
        task.stop()
        task.wait(timeout=2)
        assert calls[0] >= 2


class TestWorker:
    def test_add_starts_task(self) -> None:
        worker = Worker(_LOGGER)
        event = threading.Event()
        worker.add(Task(event.set, _LOGGER, name="setter"))
        event.wait(timeout=2)
        assert event.is_set()
        worker.stop()
        worker.wait(timeout=2)

    def test_duplicate_name_raises(self) -> None:
        worker = Worker(_LOGGER)
        worker.add(Task(lambda: None, _LOGGER, name="dup"))
        with pytest.raises(ValueError, match="Duplicate"):
            worker.add(Task(lambda: None, _LOGGER, name="dup"))
        worker.stop()
        worker.wait(timeout=2)

    def test_remove_stops_task(self) -> None:
        worker = Worker(_LOGGER)
        counter = [0]
        task = CycleTask(lambda: counter.__setitem__(0, counter[0] + 1), _LOGGER, seconds=0.01, name="rem")
        worker.add(task)
        time.sleep(0.05)
        worker.remove("rem")
        time.sleep(0.05)
        snapshot = counter[0]
        time.sleep(0.05)
        assert counter[0] == snapshot

    def test_run_and_cycle_shortcuts(self) -> None:
        worker = Worker(_LOGGER)
        once_result: list[int] = []
        cycle_counter = [0]

        worker.run(lambda: once_result.append(1), name="quick").wait(timeout=2)
        worker.cycle(lambda: cycle_counter.__setitem__(0, cycle_counter[0] + 1), seconds=0.02, name="cyc")
        time.sleep(0.1)
        worker.stop()
        worker.wait(timeout=2)

        assert once_result == [1]
        assert cycle_counter[0] >= 2

    def test_wait_respects_timeout(self) -> None:
        worker = Worker(_LOGGER)
        worker.add(Task(lambda: time.sleep(10), _LOGGER, name="slow"))
        start = time.monotonic()
        worker.stop()
        worker.wait(timeout=0.2)
        assert time.monotonic() - start < 1

    def test_active_returns_running_only(self) -> None:
        worker = Worker(_LOGGER)
        event = threading.Event()
        worker.add(Task(event.wait, _LOGGER, name="blocker"))
        worker.add(Task(lambda: None, _LOGGER, name="instant"))
        time.sleep(0.05)
        active_names = {t.name for t in worker.active}
        assert "blocker" in active_names
        event.set()
        worker.stop()
        worker.wait(timeout=2)

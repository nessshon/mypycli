import time
from pathlib import Path

import pytest

from mypycli.application import Application
from mypycli.modules import Module


class AlphaModule(Module):
    name = "alpha"
    mandatory = True

    def check(self) -> None:
        pass


class BetaModule(Module):
    name = "beta"
    mandatory = True

    def check(self) -> None:
        pass


@pytest.fixture()
def app(tmp_path: Path) -> Application:
    locales = tmp_path / "locales"
    locales.mkdir()
    return Application(
        "testapp",
        "Test App",
        False,
        work_dir=tmp_path / "work",
        logs_dir=tmp_path / "logs",
        locales_dir=locales,
        language_code="en",
    )


def test_same_method_name_across_modules_does_not_collide(app: Application) -> None:
    alpha, beta = AlphaModule(app), BetaModule(app)
    try:
        alpha.run_cycle(alpha.check, seconds=60)
        beta.run_cycle(beta.check, seconds=60)
        with pytest.raises(ValueError, match="already registered"):
            alpha.run_task(alpha.check)
    finally:
        app.worker.stop_all()


def test_run_cycle_executes(app: Application) -> None:
    ticks: list[int] = []
    alpha = AlphaModule(app)
    task = alpha.run_cycle(lambda: ticks.append(1), seconds=60, name="tick")
    try:
        deadline = time.time() + 2
        while not ticks and time.time() < deadline:
            time.sleep(0.01)
    finally:
        task.stop()
        app.worker.stop_all()
    assert ticks

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from mypycli.cli.commands._shared import exit_with_failures, require_install
from mypycli.modules.interfaces.updatable import Updatable

if TYPE_CHECKING:
    from mypycli.application import Application


def run_update(app: Application[Any]) -> None:
    """Invoke ``on_update`` on every Updatable module in registration order.

    Each module decides whether it needs work and reports progress itself;
    failures are logged and collected, the run continues, and a non-zero exit
    code is returned if any module raised.

    :raises SystemExit: If a mandatory Installable module is not installed, or
        if at least one module's ``on_update`` raised.
    """
    app.start()
    try:
        require_install(app)

        failed: list[tuple[str, Exception]] = []
        for module in app.modules.by_interface(Updatable):
            try:
                module.on_update()
            except Exception as exc:  # noqa: PERF203 — continue-on-error is intentional
                app.logger.exception(f"Update failed: {module.name}")
                failed.append((module.name, exc))

        exit_with_failures("Update", failed)
    finally:
        app.stop()

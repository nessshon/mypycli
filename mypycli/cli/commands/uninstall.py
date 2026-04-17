from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any

from mypycli.cli.commands._shared import exit_with_failures
from mypycli.modules.interfaces.installable import Installable

if TYPE_CHECKING:
    from mypycli.application import Application


def run_uninstall(app: Application[Any]) -> None:
    """Call ``on_uninstall`` on every installed Installable module in reverse order.

    Framework does not delete files or the DB itself; cleanup of services, files
    and persisted data is the module's responsibility. Per-module failures are
    logged and reported but do not stop the run.

    :param app: Application whose installed Installable modules are torn down.
    :raises SystemExit: On non-interactive stdin or if any ``on_uninstall`` raised.
    """
    app.start()
    try:
        if not sys.stdin.isatty():
            print("Refusing to uninstall in non-interactive mode", file=sys.stderr)
            raise SystemExit(1)
        if not app.console.confirm(f"Uninstall {app.label}? This cannot be undone.", default=False):
            print("Uninstall cancelled.")
            return

        failed: list[tuple[str, Exception]] = []
        for module in reversed(app.modules.by_interface(Installable)):
            try:
                module.on_uninstall()
            except Exception as exc:  # noqa: PERF203 — continue-on-error is intentional
                app.logger.exception(f"Uninstall failed: {module.name}")
                failed.append((module.name, exc))

        exit_with_failures("Uninstall", failed)
    finally:
        app.stop()

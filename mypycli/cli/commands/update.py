from __future__ import annotations

from typing import TYPE_CHECKING, Any

from mypycli.cli.commands._shared import exit_with_failures, require_install
from mypycli.modules.interfaces.updatable import Updatable

if TYPE_CHECKING:
    from mypycli.application import Application


def run_update(app: Application[Any]) -> None:
    """Invoke ``on_update`` on every Updatable module, owning the UI and logging.

    The CLI reads ``module.version`` before and after ``on_update``, prints one
    summary row per module via ``console.print_update_result`` and emits the
    matching log lines on the module's child logger. Modules are silent workers:
    they neither print nor log the update outcome themselves. Failures are
    logged with traceback, collected, and the run continues; a non-zero exit
    code is returned if any module raised.

    :raises SystemExit: If a mandatory Installable module is not installed, or
        if at least one module's ``on_update`` raised.
    """
    app.start()
    try:
        require_install(app)

        failed: list[tuple[str, Exception]] = []
        for module in app.modules.by_interface(Updatable):
            before = module.version
            module.logger.info(f"update check (current: {before})")
            try:
                module.on_update()
            except Exception as exc:  # noqa: PERF203 — continue-on-error is intentional
                module.logger.exception("update failed")
                failed.append((module.name, exc))
                app.console.print_update_result(module.name, status="failed")
                continue
            after = module.version
            if before == after:
                module.logger.info(f"already up to date ({before})")
                app.console.print_update_result(module.name, status="up_to_date")
            else:
                module.logger.info(f"updated {before} -> {after}")
                app.console.print_update_result(
                    module.name, status="updated", before=before, after=after,
                )

        exit_with_failures("Update", failed)
    finally:
        app.stop()

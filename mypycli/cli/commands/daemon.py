from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any

from mypycli.cli.commands._shared import require_install
from mypycli.modules.interfaces.daemonic import Daemonic

if TYPE_CHECKING:
    from mypycli.application import Application


def run_daemon(app: Application[Any]) -> None:
    """Run the application as a background daemon; ``Startable`` hooks are console-only."""
    running, pid = app.is_running()
    if running:
        print(f"Daemon already running (pid={pid})", file=sys.stderr)
        raise SystemExit(1)

    if not app.modules.by_interface(Daemonic, enabled_only=False):
        print("No daemonic modules registered, nothing to run.", file=sys.stderr)
        raise SystemExit(1)

    app.start()
    require_install(app)

    app.write_pid()
    try:
        for dm in app.modules.by_interface(Daemonic):
            dm.on_daemon()
        app.run_forever()
    except Exception:
        app.logger.exception("Daemon failed")
        raise
    finally:
        app.stop()
        app.remove_pid()

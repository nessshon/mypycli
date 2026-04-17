from __future__ import annotations

from typing import TYPE_CHECKING, Any

from mypycli.cli.commands._shared import require_install
from mypycli.modules.interfaces.commandable import Commandable
from mypycli.modules.interfaces.startable import Startable

if TYPE_CHECKING:
    from mypycli.application import Application


def run_console(app: Application[Any]) -> None:
    """Run the interactive REPL, wiring module commands and start/stop hooks.

    :param app: Application whose console, Startable and Commandable modules drive the REPL.
    :raises SystemExit: If a mandatory Installable module is not installed.
    """
    app.start()
    require_install(app)
    started: list[Startable] = []
    try:
        for module in app.modules.by_interface(Startable):
            module.on_start()
            started.append(module)
        for cmd_module in app.modules.by_interface(Commandable):
            for cmd in cmd_module.get_commands():
                app.console.add_command(cmd)
        app.console.run()
    finally:
        for module in reversed(started):
            module.on_stop()
        app.stop()

from __future__ import annotations

import shutil
import sys
from typing import TYPE_CHECKING, Any

from mypycli.cli.commands import (
    run_console,
    run_daemon,
    run_install,
    run_logs,
    run_uninstall,
    run_update,
)
from mypycli.cli.parser import build_parser
from mypycli.utils.system import is_root

if TYPE_CHECKING:
    from mypycli.application import Application


_ROOT_REQUIRED = frozenset({"install", "update", "uninstall"})


def run(app: Application[Any]) -> None:
    """Parse CLI arguments and dispatch to daemon, install, uninstall, update or REPL mode.

    ``install``/``update``/``uninstall`` are refused with ``SystemExit(1)`` and a
    hint to re-run via ``sudo`` or ``su`` when the current user is not root.
    Converts ``KeyboardInterrupt`` into ``SystemExit(130)`` with a cancellation message.

    :param app: Application whose modules and console drive the dispatched command.
    :raises SystemExit: On missing root, ``KeyboardInterrupt``, or any ``SystemExit`` raised by commands.
    """
    parser = build_parser(app)
    args = parser.parse_args()
    command = getattr(args, "command", None)

    if command in _ROOT_REQUIRED and not is_root():
        _exit_not_root(app.name, command)

    try:
        if command == "daemon":
            run_daemon(app)
        elif command == "install":
            run_install(app)
        elif command == "update":
            run_update(app)
        elif command == "uninstall":
            run_uninstall(app)
        elif command == "logs":
            run_logs(
                app,
                lines=getattr(args, "lines", 50),
                follow=getattr(args, "follow", False),
                level=getattr(args, "level", None),
                module=getattr(args, "module", None),
                include_rotated=getattr(args, "include_rotated", False),
            )
        else:
            run_console(app)
    except KeyboardInterrupt:
        label = command or "operation"
        print(f"\n{label.capitalize()} cancelled.", file=sys.stderr)
        raise SystemExit(130) from None


def _exit_not_root(app_name: str, command: str) -> None:
    """Print a stderr hint describing how to re-run ``command`` as root, then exit(1).

    Picks ``sudo`` when available, falls back to ``su -c '<cmd>'``; if neither is on
    PATH the hint collapses to a plain ``Run as root.`` line.
    """
    if shutil.which("sudo"):
        hint = f"Try: sudo {app_name} {command}"
    elif shutil.which("su"):
        hint = f"Try: su -c '{app_name} {command}'"
    else:
        hint = "Run as root."
    print(f"'{command}' requires root. {hint}", file=sys.stderr)
    raise SystemExit(1)

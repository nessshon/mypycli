from __future__ import annotations

import argparse
from typing import TYPE_CHECKING, Any

from mypycli.modules.interfaces.daemonic import Daemonic
from mypycli.modules.interfaces.installable import Installable
from mypycli.modules.interfaces.updatable import Updatable

if TYPE_CHECKING:
    from mypycli.application import Application


def build_parser(app: Application[Any]) -> argparse.ArgumentParser:
    """Build the top-level argparse parser with subcommands per module interface.

    Subcommands appear only when at least one module implements the matching
    interface: ``daemon`` for Daemonic; ``install``/``uninstall`` for Installable;
    ``update`` for Updatable. With no subcommand the app enters REPL mode.

    :param app: Application whose ``name`` and registered modules shape the parser.
    """
    parser = argparse.ArgumentParser(prog=app.name)
    subparsers = parser.add_subparsers(dest="command")

    if app.modules.by_interface(Daemonic, enabled_only=False):
        subparsers.add_parser("daemon", help="Run in daemon mode")

    if app.modules.by_interface(Installable, enabled_only=False):
        subparsers.add_parser("install", help="Install the application")
        subparsers.add_parser("uninstall", help="Uninstall the application")

    if app.modules.by_interface(Updatable, enabled_only=False):
        subparsers.add_parser("update", help="Update all Updatable modules")

    logs_p = subparsers.add_parser("logs", help="Show the application log file")
    logs_p.add_argument("-n", "--lines", type=int, default=50, help="Trailing lines to print")
    logs_p.add_argument("-f", "--follow", action="store_true", help="Follow new lines as they are appended")
    logs_p.add_argument(
        "--level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Minimum level to include",
    )
    logs_p.add_argument("--module", help="Filter by logger-name suffix (e.g. 'system' matches 'demo.system')")
    logs_p.add_argument(
        "--all",
        action="store_true",
        dest="include_rotated",
        help="Include rotated .N backups, oldest first",
    )

    return parser

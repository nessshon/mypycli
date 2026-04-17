from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING

from mypycli.console.ansi import colorize_text
from mypycli.i18n.internal import _
from mypycli.modules.interfaces import ALL_INTERFACES
from mypycli.modules.interfaces.statusable import Statusable
from mypycli.modules.interfaces.updatable import Updatable
from mypycli.types import BoxStyle, Color, ColorText
from mypycli.utils.errors import format_validation_error

if TYPE_CHECKING:
    from typing import Any

    from mypycli.application import Application


def cmd_help(app: Application[Any], args: list[str]) -> None:
    """Print the command listing, or the subcommand listing if a group name is given in ``args``.

    :param app: Owning application exposing the console and registered commands.
    :param args: Command-line arguments; ``args[0]`` optionally selects a command group.
    """
    commands = app.console.list_commands()
    if args:
        for cmd in commands:
            if str(cmd.name) == args[0] and cmd.children:
                app.console.print_help(cmd.children)
                return
        print(colorize_text(_("console.no_help_for", name=args[0]), Color.YELLOW))
    else:
        app.console.print_help(commands)


def cmd_versions(app: Application[Any], _args: list[str]) -> None:
    """Print a Component/Version table with the framework row first, followed by Updatable modules.

    :param app: Owning application exposing the console and module registry.
    :param _args: Unused command-line arguments.
    """
    rows: list[list[str | ColorText]] = [
        [ColorText(_("console.table.component"), Color.CYAN), ColorText(_("console.table.version"), Color.CYAN)],
    ]
    rows.extend([module.name, module.version] for module in app.modules.by_interface(Updatable))
    app.console.print_table(rows)


def cmd_history(app: Application[Any], _args: list[str]) -> None:
    """Print the recorded REPL command history with timestamps.

    :param app: Owning application exposing the console and its history.
    :param _args: Unused command-line arguments.
    """
    history = app.console.history
    if not history:
        print(colorize_text(_("console.no_history"), Color.YELLOW))
        return
    for timestamp, command in history:
        ts = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
        print(f"  {colorize_text(ts, Color.CYAN)}  {command}")


def cmd_clear(_app: Application[Any], _args: list[str]) -> None:
    """Clear the terminal screen and move the cursor home.

    :param _app: Unused owning application.
    :param _args: Unused command-line arguments.
    """
    print("\033[2J\033[H", end="")


def cmd_exit(app: Application[Any], _args: list[str]) -> None:
    """Signal the REPL loop to exit on its next iteration.

    :param app: Owning application whose console loop will be stopped.
    :param _args: Unused command-line arguments.
    """
    app.console.stop()


def cmd_modules(app: Application[Any], _args: list[str]) -> None:
    """Print a plain table of all registered modules with enabled, mandatory flags and capabilities.

    :param app: Owning application exposing the console and module registry.
    :param _args: Unused command-line arguments.
    """
    rows: list[list[str | ColorText]] = [
        [
            ColorText(_("console.table.name"), Color.CYAN),
            ColorText(_("console.table.enabled"), Color.CYAN),
            ColorText(_("console.table.mandatory"), Color.CYAN),
            ColorText(_("console.table.capabilities"), Color.CYAN),
        ],
    ]
    rows.extend(
        [
            module.name,
            ColorText(_("console.table.yes"), Color.GREEN) if module.is_enabled
                else ColorText(_("console.table.no"), Color.RED),
            ColorText(_("console.table.yes"), Color.GREEN) if module.mandatory
                else _("console.table.no"),
            _module_capabilities(module),
        ]
        for module in app.modules.all(enabled_only=False)
    )
    app.console.print_table(rows, style=BoxStyle.ROUNDED)


def _module_capabilities(module: object) -> str:
    """Return a comma-separated list of interface names (lowercased) implemented by ``module``.

    :param module: Module instance whose implemented interfaces are inspected.
    """
    names = [iface.__name__.lower() for iface in ALL_INTERFACES if isinstance(module, iface)]
    return ", ".join(names) if names else "-"


def cmd_db(app: Application[Any], _args: list[str]) -> None:
    """Pretty-print the full application database as colored JSON.

    :param app: Owning application exposing the console and database.
    :param _args: Unused command-line arguments.
    """
    app.console.print_json(app.db.all_data())


def cmd_db_get(app: Application[Any], args: list[str]) -> None:
    """Print a database field value selected by a dot-separated path in ``args[0]``.

    :param app: Owning application exposing the console and database.
    :param args: Command-line arguments; ``args[0]`` is the dot-separated field path.
    """
    if not args:
        print(colorize_text(_("console.db_get_usage"), Color.RED))
        return
    found, value = app.db.get_by_path(args[0])
    if not found:
        print(colorize_text(_("console.field_not_found", path=args[0]), Color.RED))
        return
    key = colorize_text(args[0], Color.CYAN)
    if isinstance(value, (dict, list)):
        print(f"{key}:")
        app.console.print_json(value)
    else:
        print(f"{key}: ", end="")
        app.console.print_json(value)


def cmd_db_set(app: Application[Any], args: list[str]) -> None:
    """Set a database field (``args[0]``) to a value (``args[1:]``), parsed as JSON or bare string, then persist.

    :param app: Owning application exposing the console and database.
    :param args: Command-line arguments; ``args[0]`` is the field path and ``args[1:]`` form the value.
    """
    if len(args) < 2:
        print(colorize_text(_("console.db_set_usage"), Color.RED))
        return
    path = args[0]
    raw = " ".join(args[1:])
    if path == "language":
        available = app.translator.available_languages()
        if raw not in available:
            print(colorize_text(
                _("console.unknown_language", code=raw, available=", ".join(sorted(available))),
                Color.RED,
            ))
            return
    found, old_value = app.db.get_by_path(path)
    try:
        app.db.set_by_path_str(path, raw)
    except KeyError:
        print(colorize_text(_("console.field_not_found", path=path), Color.RED))
        return
    except ValueError as exc:
        print(colorize_text(_("console.validation_error", error=format_validation_error(exc)), Color.RED))
        return
    _found, new_value = app.db.get_by_path(path)
    _print_field_change(path, old_value if found else None, new_value)
    if path in ("language", "debug"):
        print(colorize_text(_("console.restart_hint"), Color.YELLOW))


def _print_field_change(field: str, old: object, new: object) -> None:
    """Print a diff-style representation of a field change.

    :param field: Dot-separated path of the changed field.
    :param old: Previous value (``None`` if the field did not exist).
    :param new: New value after the update.
    """
    key = colorize_text(field, Color.CYAN)
    is_complex = isinstance(old, (dict, list)) or isinstance(new, (dict, list))
    if is_complex:
        old_str = colorize_text(json.dumps(old, indent=2, default=str), Color.RED)
        new_str = colorize_text(json.dumps(new, indent=2, default=str), Color.GREEN)
        print(f"{key}:")
        print(old_str)
        print(new_str)
    else:
        old_str = colorize_text(json.dumps(old, default=str), Color.RED)
        new_str = colorize_text(json.dumps(new, default=str), Color.GREEN)
        print(f"{key}: {old_str} \u2192 {new_str}")


def cmd_status(app: Application[Any], _args: list[str]) -> None:
    """Invoke ``show_status()`` on every Statusable module; the app owns the display."""
    for module in app.modules.by_interface(Statusable):
        module.show_status()

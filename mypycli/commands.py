from __future__ import annotations

import datetime
import sys
from typing import TYPE_CHECKING

from mypycli.modules import Installable, Statusable, Updatable
from mypycli.types import Color

if TYPE_CHECKING:
    from argparse import Namespace

    from rich.text import Text

    from mypycli.application import Application


def cmd_status(app: Application, _args: list[str]) -> bool:
    for module in app.modules.get_by_interface(Statusable):
        module.print_status()
    return True


def cmd_modules(app: Application, _args: list[str]) -> bool:
    rows: list[list[str | Text]] = [
        [
            Color.cyan(app.translate("mypycli.common.name")),
            Color.cyan(app.translate("mypycli.common.state")),
            Color.cyan(app.translate("mypycli.common.mandatory")),
        ],
    ]
    rows.extend(
        [
            module.name,
            Color.green(app.translate("mypycli.common.enabled"))
            if module.is_enabled
            else Color.red(app.translate("mypycli.common.disabled")),
            Color.green(app.translate("mypycli.common.yes"))
            if module.mandatory
            else Color.yellow(app.translate("mypycli.common.no")),
        ]
        for module in app.modules.get_all(enabled_only=False)
    )
    app.console.print_table(rows)
    return True


def cmd_versions(app: Application, _args: list[str]) -> bool:
    rows: list[list[str | Text]] = [
        [
            Color.cyan(app.translate("mypycli.common.component")),
            Color.cyan(app.translate("mypycli.common.version")),
        ],
    ]
    rows.extend([module.name, module.version] for module in app.modules.get_by_interface(Updatable))
    app.console.print_table(rows)
    return True


def cmd_history(app: Application, _args: list[str]) -> bool:
    for entry in app.history.load_entries():
        dt_string = datetime.datetime.fromtimestamp(entry.timestamp).strftime("%Y-%m-%d %H:%M:%S")
        app.console.print(Color.cyan(dt_string), entry.command, sep="  ", overflow="ellipsis")
    return True


def cmd_clear(app: Application, _args: list[str]) -> bool:
    app.console.clear()
    return True


def cmd_help(app: Application, _args: list[str]) -> bool:
    app.console.print_help(app.commands)
    return True


def cmd_exit(_app: Application, _args: list[str]) -> bool:
    return False


def cli_cmd_update(app: Application, args: Namespace) -> None:
    modules = app.modules.get_by_interface(Updatable, enabled_only=False)
    if args.module:
        modules = [m for m in modules if m.name == args.module]
        if not modules:
            app.console.error(app.translate("mypycli.cli.unknown_modules", names=args.module))
            raise SystemExit(1)

    rows: list[list[str | Text]] = [
        [
            Color.cyan(app.translate("mypycli.common.component")),
            Color.cyan(app.translate("mypycli.common.before")),
            Color.cyan(app.translate("mypycli.common.after")),
        ],
    ]
    failed = False
    for module in modules:
        version_before = module.version
        try:
            module.on_update()
        except Exception:
            failed = True
            app.logger.exception(f"update failed: {module.name}")
            app.console.error(app.translate("mypycli.cli.update_failed", name=module.name))
            rows.append([module.name, version_before, Color.red(app.translate("mypycli.common.failed"))])
            continue
        rows.append([module.name, version_before, module.version])
    app.console.print_table(rows)
    if failed:
        raise SystemExit(1)


def cli_cmd_install(app: Application, args: Namespace) -> None:
    modules = app.modules.get_by_interface(Installable, enabled_only=False)
    optional = [m.name for m in modules if not m.mandatory]
    choices = [m.name for m in modules if not m.mandatory and not m.is_enabled]

    if args.modules is not None:
        selected = [name for name in args.modules.split(",") if name]
        unknown = sorted(set(selected) - set(optional))
        if unknown:
            app.console.error(app.translate("mypycli.cli.unknown_modules", names=", ".join(unknown)))
            raise SystemExit(1)
    elif choices and sys.stdin.isatty():
        selected = app.prompt.ask_multiselect(
            app.translate("mypycli.cli.select_modules"),
            choices=choices,
            defaults=choices,
        )
    else:
        selected = []

    for module in modules:
        if not module.mandatory and module.name not in selected:
            continue
        try:
            module.on_install()
        except Exception:
            app.logger.exception(f"install failed: {module.name}")
            app.console.error(app.translate("mypycli.cli.install_failed", name=module.name))
            raise SystemExit(1) from None
        app.console.success(app.translate("mypycli.cli.installed", name=module.name))


def cli_cmd_uninstall(app: Application, args: Namespace) -> None:
    confirm = args.yes or app.prompt.ask_confirm(app.translate("mypycli.cli.uninstall_confirm"), default=False)
    if not confirm:
        return

    for module in reversed(app.modules.get_by_interface(Installable, enabled_only=False)):
        try:
            module.on_uninstall()
        except Exception:
            app.logger.exception(f"uninstall failed: {module.name}")
            app.console.error(app.translate("mypycli.cli.uninstall_failed", name=module.name))
            continue
        app.console.success(app.translate("mypycli.cli.uninstalled", name=module.name))

from __future__ import annotations

import os
import shlex
import sys
from argparse import ArgumentParser
from pathlib import Path

from mypycli.commands import (
    cli_cmd_install,
    cli_cmd_uninstall,
    cli_cmd_update,
    cmd_clear,
    cmd_exit,
    cmd_help,
    cmd_history,
    cmd_modules,
    cmd_status,
    cmd_versions,
)
from mypycli.components import (
    Console,
    Daemon,
    History,
    Logger,
    Prompt,
    Translator,
    Worker,
)
from mypycli.modules import (
    Commandable,
    Installable,
    Module,
    ModuleRegistry,
    Startable,
    Updatable,
)
from mypycli.types import CliCommand, Command, CommandGroup, Mode
from mypycli.utils.system import find_root_tool, is_root, system_language


class Application:
    def __init__(
        self,
        name: str,
        label: str,
        debug: bool,
        *,
        work_dir: str | Path,
        logs_dir: str | Path,
        locales_dir: str | Path,
        history_limit: int = 100,
        language_code: str | None = None,
    ) -> None:
        if language_code is None:
            language_code = system_language()

        self.name = name
        self.label = label
        self.mode: Mode | None = None

        self.work_dir = Path(work_dir)
        self.logs_dir = Path(logs_dir)
        self.locales_dir = Path(locales_dir)

        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        self.worker = Worker(name)
        self.console = Console()
        self.modules = ModuleRegistry()
        self.logger = Logger(name, debug, self.logs_dir)
        self.history = History(self.work_dir, name, history_limit)
        self.translator = Translator(self.locales_dir, language_code)

        self.daemon = Daemon(self)
        self.prompt = Prompt(self)

        self.cli_parser = ArgumentParser()
        self.cli_parser.set_defaults(handler=None, needs_root=False)
        self.cli_parser.add_argument("--daemon", action="store_true")
        self.cli_subparsers = self.cli_parser.add_subparsers(dest="command")

    @property
    def commands(self) -> list[Command | CommandGroup]:
        module_commands: list[Command | CommandGroup] = []
        for module in self.modules.get_by_interface(Commandable, enabled_only=False):
            module_commands.extend(module.commands)

        builtins_commands = [
            Command("status", cmd_status, description=self.translate("mypycli.commands.status")),
            Command("modules", cmd_modules, description=self.translate("mypycli.commands.modules")),
            Command("versions", cmd_versions, description=self.translate("mypycli.commands.versions")),
            Command("history", cmd_history, description=self.translate("mypycli.commands.history")),
            Command("clear", cmd_clear, description=self.translate("mypycli.commands.clear")),
            Command("help", cmd_help, description=self.translate("mypycli.commands.help")),
            Command("exit", cmd_exit, description=self.translate("mypycli.commands.exit")),
        ]
        return module_commands + builtins_commands

    @property
    def translate(self) -> Translator:
        return self.translator

    def register_module(self, module_cls: type[Module]) -> None:
        module = module_cls(self)
        self.modules.register(module)

    def register_cli_command(self, cli_command: CliCommand) -> ArgumentParser:
        command = self.cli_subparsers.add_parser(cli_command.name, help=cli_command.description)
        command.set_defaults(handler=cli_command.handler, needs_root=cli_command.needs_root)
        return command

    def run(self) -> None:
        self._dispatch_cli_command()

    def _run_mode(self, mode: Mode) -> None:
        self.mode = mode
        self.logger.set_prefix(self.mode)

        started: list[Startable] = []
        try:
            if self.mode == Mode.PROMPT:
                for startable_module in self.modules.get_by_interface(Startable):
                    startable_module.on_start()
                    started.append(startable_module)
                self.prompt.run()
            else:
                self.daemon.run()
        finally:
            self.worker.stop_all()
            for startable_module in reversed(started):
                try:
                    startable_module.on_stop()
                except Exception:
                    self.logger.exception(f"stop failed: {startable_module.name}")
            for module in self.modules.get_all(enabled_only=False):
                module.close_async_loop()
            self.mode = None

    def _dispatch_cli_command(self) -> None:
        self._register_builtin_cli_commands()
        args = self.cli_parser.parse_args()

        if args.handler is not None:
            if args.command:
                self.logger.set_prefix(args.command)
            if args.needs_root and not is_root():
                try:
                    root_tool = find_root_tool()
                    orig_cmd = list(sys.orig_argv)

                    if root_tool == "sudo":
                        os.execvp("sudo", ["sudo", "-E", "--", *orig_cmd])
                    else:
                        os.execvp("su", ["su", "-c", shlex.join(orig_cmd)])
                except RuntimeError:
                    raise SystemExit(1) from None
            try:
                args.handler(self, args)
            except KeyboardInterrupt:
                self.console.warning(self.translate("mypycli.error.user_canceled"))
                raise SystemExit(130) from None
            return

        mode = Mode.DAEMON if args.daemon else Mode.PROMPT
        try:
            self._run_mode(mode)
        except RuntimeError as e:
            self.logger.exception("startup failed")
            self.console.error(str(e))
            raise SystemExit(1) from None

    def _register_builtin_cli_commands(self) -> None:
        if self.modules.get_by_interface(Updatable, enabled_only=False):
            update = self.register_cli_command(
                CliCommand(
                    name="update",
                    description=self.translate("mypycli.cli_commands.update"),
                    handler=cli_cmd_update,
                    needs_root=True,
                )
            )
            update.add_argument("module", nargs="?")
        if self.modules.get_by_interface(Installable, enabled_only=False):
            install = self.register_cli_command(
                CliCommand(
                    name="install",
                    description=self.translate("mypycli.cli_commands.install"),
                    handler=cli_cmd_install,
                    needs_root=True,
                )
            )
            install.add_argument("--modules")
            uninstall = self.register_cli_command(
                CliCommand(
                    name="uninstall",
                    description=self.translate("mypycli.cli_commands.uninstall"),
                    handler=cli_cmd_uninstall,
                    needs_root=True,
                )
            )
            uninstall.add_argument("--yes", action="store_true")

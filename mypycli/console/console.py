"""Two-channel model: ``Console`` drives stdout for the REPL; the logger writes to the log file.

Call ``self.logger.*`` for diagnostics (always go to the file), and
``self.app.console.*`` for interactive UX (stdout, REPL-only). Do not mix them:
in daemon mode the console is never invoked, and the logger is never routed
to stdout.
"""

from __future__ import annotations

import readline
import sys
import time as _time
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from mypycli.console.ansi import colorize_text, render_color_text
from mypycli.console.builtin import (
    cmd_clear,
    cmd_db,
    cmd_db_get,
    cmd_db_set,
    cmd_exit,
    cmd_help,
    cmd_history,
    cmd_modules,
    cmd_status,
    cmd_versions,
)
from mypycli.console.input import ConsoleInput
from mypycli.console.output import ConsoleOutput
from mypycli.console.progress import ProgressLine
from mypycli.database import Database, DatabaseSchema
from mypycli.i18n.internal import _
from mypycli.types import Color, ColorText, Command, Confirm, Input, Multiselect, Secret, Select

if TYPE_CHECKING:
    from typing import Any

    from mypycli.application import Application


class _HistoryEntry(BaseModel):
    timestamp: float
    command: str


class _HistorySchema(DatabaseSchema):
    entries: list[_HistoryEntry] = Field(default_factory=list)


def _resolve_message(value: str | ColorText | None, default: str) -> str:
    """Resolve a banner message value.

    :param value: ``None`` selects ``default``; ``""`` disables the banner; otherwise rendered to ANSI.
    :param default: Fallback banner string used when ``value`` is ``None``.
    :returns: Final banner string, or ``""`` when disabled.
    """
    if value is None:
        return default
    return render_color_text(value) if value else ""


class Console(ConsoleOutput, ConsoleInput):
    """Interactive REPL with command dispatch, persisted history and readline tab-completion.

    :param app: Owning application; used for labels, logger, work dir and module access.
    :param welcome: Welcome banner shown before the loop; ``None`` selects the default banner, ``""`` disables it.
    :param goodbye: Goodbye banner shown after the loop; ``None`` selects the default banner, ``""`` disables it.
    """

    def __init__(
        self,
        app: Application[Any],
        *,
        welcome: str | ColorText | None = None,
        goodbye: str | ColorText | None = None,
    ) -> None:
        self.app = app

        self._running = False
        self._commands: list[Command] = []
        self._history_limit = 100
        self._history_db: Database[_HistorySchema] | None = None

        self._welcome_raw = welcome
        self._goodbye_raw = goodbye
        self._welcome: str = ""
        self._goodbye: str = ""

    def _resolve_banners(self) -> None:
        default_welcome = _(
            "console.welcome",
            label=colorize_text(self.app.label, Color.CYAN),
            help=colorize_text("help", Color.GREEN),
        )
        default_goodbye = colorize_text(
            _("console.goodbye", label=self.app.label), Color.YELLOW
        )
        self._welcome = _resolve_message(self._welcome_raw, default_welcome)
        self._goodbye = _resolve_message(self._goodbye_raw, default_goodbye)

    def add_command(self, command: Command) -> None:
        """Register a user-defined command alongside the built-ins.

        :param command: Command to append to the user-registered command list.
        """
        self._commands.append(command)

    def stop(self) -> None:
        """Signal the REPL loop to exit on its next iteration."""
        self._running = False

    def list_commands(self) -> list[Command]:
        """Return the full command list including built-ins and user-registered commands."""
        return self._all_commands()

    @property
    def history(self) -> list[tuple[float, str]]:
        """Return persisted REPL history as ``(timestamp, command)`` tuples; empty before ``run`` loads it."""
        if self._history_db is None:
            return []
        return [(e.timestamp, e.command) for e in self._history_db.data.entries]

    def ask(self, question: Input | Secret | Confirm | Select | Multiselect) -> str | bool | list[str]:
        """Dispatch a question object to the matching prompt method based on its type.

        :param question: Question instance whose type selects the prompt method to invoke.
        :returns: ``str`` for Input/Secret/Select, ``bool`` for Confirm, ``list[str]`` for Multiselect.
        :raises TypeError: If ``question`` is not one of the supported question types.
        """
        if isinstance(question, Input):
            return self.input(question.prompt, default=question.default, validate=question.validate)
        if isinstance(question, Secret):
            return self.secret(question.prompt, validate=question.validate)
        if isinstance(question, Confirm):
            return self.confirm(question.prompt, default=question.default)
        if isinstance(question, Select):
            return self.select(question.prompt, question.choices)
        if isinstance(question, Multiselect):
            return self.multiselect(question.prompt, question.choices)
        raise TypeError(f"Unknown question type: {type(question).__name__}")

    def print_progress(self, *, total: int | None = None) -> ProgressLine:
        """Return a ``ProgressLine`` context manager tied to stdout.

        See ``ProgressLine`` for rendering details.

        :param total: Expected number of ``update`` calls; enables the ``[n/total]`` prefix.
        :raises ValueError: ``total`` is not a positive integer.
        """
        if total is not None and total < 1:
            raise ValueError("total must be a positive integer")
        return ProgressLine(sys.stdout, tty=sys.stdout.isatty(), total=total)

    def run(self) -> None:
        """Run the REPL loop until the user exits; prints welcome, loads history, and prints goodbye on exit.

        Exits cleanly on ``Ctrl+C``, ``EOF``, or when a command calls ``stop()``.
        """
        self._resolve_banners()
        self._print_welcome()
        self._load_history()
        self._setup_readline()
        self._running = True

        while self._running:
            try:
                prompt = f"{colorize_text(self.app.name, Color.YELLOW)}> "
                raw = input(prompt).strip()
            except (KeyboardInterrupt, EOFError):
                print()
                break

            if not raw:
                continue

            self._record_history(raw)
            readline.add_history(raw)
            self._dispatch(parts=raw.split())

        if self._goodbye:
            print(self._goodbye)

    def _dispatch(self, parts: list[str]) -> None:
        cmd_name = parts[0]
        args = parts[1:]

        for cmd in self._all_commands():
            if str(cmd.name) == cmd_name:
                self._execute_command(cmd, args)
                return

        print(colorize_text(_("console.unknown_command", name=cmd_name), Color.RED))

    def _execute_command(self, cmd: Command, args: list[str]) -> None:
        if cmd.children and args:
            for child in cmd.children:
                if str(child.name) == args[0]:
                    self._execute_command(child, args[1:])
                    return

        if cmd.handler is not None:
            try:
                cmd.handler(self.app, args)
            except Exception as err:
                self.app.logger.exception(f"Command '{cmd.name}' failed")
                print(colorize_text(_("console.command_error", error=err), Color.RED))
        elif cmd.children:
            self.print_help(cmd.children)

    def _all_commands(self) -> list[Command]:
        return [
            Command(
                "db",
                description=_("console.commands.db"),
                children=[
                    Command("show", cmd_db, _("console.commands.db_show")),
                    Command("get", cmd_db_get, _("console.commands.db_get"), usage="<field>"),
                    Command("set", cmd_db_set, _("console.commands.db_set"), usage="<field> <value>"),
                ],
            ),
            *self._commands,
            Command("status", cmd_status, _("console.commands.status")),
            Command("modules", cmd_modules, _("console.commands.modules")),
            Command("versions", cmd_versions, _("console.commands.versions")),
            Command("history", cmd_history, _("console.commands.history")),
            Command("clear", cmd_clear, _("console.commands.clear")),
            Command(ColorText("help", Color.GREEN), cmd_help, _("console.commands.help")),
            Command(ColorText("exit", Color.RED), cmd_exit, _("console.commands.exit")),
        ]

    def _print_welcome(self) -> None:
        if self._welcome:
            print(self._welcome)

    def _load_history(self) -> None:
        history_path = self.app.work_dir / f"{self.app.name}.history"
        self._history_db = Database(_HistorySchema, history_path)
        self._history_db.load(auto_create=True)
        for entry in self._history_db.data.entries:
            readline.add_history(entry.command)

    def _record_history(self, command: str) -> None:
        if self._history_db is None:
            return
        entries = list(self._history_db.data.entries)
        entries.append(_HistoryEntry(timestamp=_time.time(), command=command))
        self._history_db.data.entries = entries[-self._history_limit :]

    def _setup_readline(self) -> None:
        readline.set_completer_delims(" ")
        readline.set_completer(self._completer)
        if "libedit" in getattr(readline, "__doc__", ""):
            readline.parse_and_bind("bind ^I rl_complete")
        else:
            readline.parse_and_bind("tab: complete")

    def _completer(self, text: str, state: int) -> str | None:
        line = readline.get_line_buffer().lstrip()
        parts = line.split()

        if not parts or (len(parts) == 1 and not line.endswith(" ")):
            options = [str(c.name) for c in self._all_commands() if str(c.name).startswith(text)]
        else:
            commands = self._all_commands()
            for part in parts[:-1] if not line.endswith(" ") else parts:
                matched = [c for c in commands if str(c.name) == part]
                if matched and matched[0].children:
                    commands = matched[0].children
                else:
                    commands = []
                    break
            options = [str(c.name) for c in commands if str(c.name).startswith(text)]

        return options[state] if state < len(options) else None

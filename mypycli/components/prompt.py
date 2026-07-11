from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from InquirerPy import get_style, inquirer
from InquirerPy.base import Choice
from prompt_toolkit import HTML, PromptSession
from prompt_toolkit.completion import NestedCompleter
from prompt_toolkit.styles import Style

from mypycli.types import Command, CommandGroup

if TYPE_CHECKING:
    from collections.abc import Callable

    from mypycli.application import Application


class Prompt:
    POINTER = "❯"
    MARK = "[×]"
    UNMARK = "[ ]"

    INQUIRER_STYLE = get_style(
        {
            "questionmark": "fg:cyan bold",
            "question": "bold",
            "input": "fg:cyan",
            "answermark": "fg:green bold",
            "answer": "fg:green bold",
            "pointer": "fg:green bold",
            "marker": "fg:green bold",
            "instruction": "fg:grey",
            "long_instruction": "fg:grey",
        }
    )

    def __init__(self, app: Application) -> None:
        self._app = app
        self._session_running = False
        self._session: PromptSession[str] | None = None

    def ask_text(
        self,
        message: str,
        *,
        default: str = "",
        instruction: str | None = None,
        bottom_instruction: str | None = None,
        validate: Callable[[str], bool] = lambda _: True,
        invalid_message: str | None = None,
        env_var: str | None = None,
    ) -> str:
        if env_var and (value := os.environ.get(env_var)):
            return value
        return inquirer.text(
            message,
            default=default,
            instruction=instruction or "",
            long_instruction=bottom_instruction or "",
            validate=validate,
            invalid_message=invalid_message or self._app.translate("mypycli.prompt.invalid_message"),
            mandatory_message=self._app.translate("mypycli.prompt.mandatory_message"),
            style=self.INQUIRER_STYLE,
        ).execute()

    def ask_number(
        self,
        message: str,
        *,
        default: int | float = 0,
        float_allowed: bool = True,
        min_allowed: int | float | None = None,
        max_allowed: int | float | None = None,
        instruction: str | None = None,
        bottom_instruction: str | None = None,
        validate: Callable[[str], bool] = lambda _: True,
        invalid_message: str | None = None,
        env_var: str | None = None,
    ) -> int | float:
        if env_var and (value := os.environ.get(env_var)):
            return float(value) if float_allowed else int(value)
        if bottom_instruction is None:
            bottom_instruction = self._app.translate("mypycli.prompt.number.bottom_instruction")
        return inquirer.number(
            message,
            default=default,
            float_allowed=float_allowed,
            min_allowed=min_allowed,
            max_allowed=max_allowed,
            instruction=instruction or "",
            long_instruction=bottom_instruction or "",
            validate=validate,
            invalid_message=invalid_message or self._app.translate("mypycli.prompt.invalid_message"),
            mandatory_message=self._app.translate("mypycli.prompt.mandatory_message"),
            style=self.INQUIRER_STYLE,
        ).execute()

    def ask_secret(
        self,
        message: str,
        *,
        instruction: str | None = None,
        bottom_instruction: str | None = None,
        validate: Callable[[str], bool] = lambda _: True,
        env_var: str | None = None,
    ) -> str:
        if env_var and (value := os.environ.get(env_var)):
            return value
        return inquirer.secret(
            message,
            instruction=instruction or "",
            long_instruction=bottom_instruction or "",
            validate=validate,
            invalid_message=self._app.translate("mypycli.prompt.invalid_message"),
            mandatory_message=self._app.translate("mypycli.prompt.mandatory_message"),
            style=self.INQUIRER_STYLE,
        ).execute()

    def ask_confirm(
        self,
        message: str,
        *,
        default: bool = True,
        instruction: str | None = None,
        bottom_instruction: str | None = None,
    ) -> bool:
        return inquirer.confirm(
            message,
            default=default,
            instruction=instruction or "",
            long_instruction=bottom_instruction or "",
            mandatory_message=self._app.translate("mypycli.prompt.mandatory_message"),
            style=self.INQUIRER_STYLE,
        ).execute()

    def ask_select(
        self,
        message: str,
        *,
        choices: list[str],
        default: str | None = None,
        pointer: str = POINTER,
        instruction: str | None = None,
        bottom_instruction: str | None = None,
        env_var: str | None = None,
    ) -> str:
        if env_var and (value := os.environ.get(env_var)):
            return value
        if bottom_instruction is None:
            bottom_instruction = self._app.translate("mypycli.prompt.select.bottom_instruction")
        return inquirer.select(
            message=message,
            choices=choices,
            default=default,
            pointer=pointer,
            instruction=instruction or "",
            long_instruction=bottom_instruction or "",
            style=self.INQUIRER_STYLE,
        ).execute()

    def ask_multiselect(
        self,
        message: str,
        *,
        choices: list[str],
        defaults: list[str] | None = None,
        pointer: str = POINTER,
        selected: str = MARK,
        unselected: str = UNMARK,
        instruction: str | None = None,
        bottom_instruction: str | None = None,
        env_var: str | None = None,
    ) -> list[str]:
        if env_var and (value := os.environ.get(env_var)):
            return value.split(",")
        if bottom_instruction is None:
            bottom_instruction = self._app.translate("mypycli.prompt.multiselect.bottom_instruction")
        defaults = defaults or []
        qchoices = [Choice(c, enabled=c in defaults) for c in choices]
        return inquirer.checkbox(
            message=message,
            choices=qchoices,
            pointer=pointer,
            enabled_symbol=selected,
            disabled_symbol=unselected,
            instruction=instruction or "",
            long_instruction=bottom_instruction or "",
            style=self.INQUIRER_STYLE,
        ).execute()

    def run(self) -> None:
        session = self._ensure_session()
        self._session_running = True
        self._app.console.print(self._app.translate("mypycli.message.welcome", label=self._app.label))

        message = HTML(f"<ansiyellow>{self._app.label}> </ansiyellow>")
        while self._session_running:
            try:
                result = session.prompt(message)
            except KeyboardInterrupt:
                continue
            except EOFError:
                break
            if not self._dispatch(result):
                break

        self._app.console.print(self._app.translate("mypycli.message.goodbye", label=self._app.label))

    def stop(self) -> None:
        self._session = None
        self._session_running = False

    def _dispatch(self, result: str) -> bool:
        parts = result.split()
        if not parts:
            return True

        candidates: list[Command | CommandGroup] = self._app.commands
        for i, part in enumerate(parts):
            match = next((c for c in candidates if c.name == part), None)
            if match is None:
                cmd_name = " ".join(parts[: i + 1])
                message = self._app.translate("mypycli.error.unknown_command", name=cmd_name)
                self._app.console.error(message)
                return True

            if isinstance(match, Command):
                args = parts[i + 1 :]
                if match.handler is not None:
                    try:
                        return match.handler(self._app, args)
                    except KeyboardInterrupt:
                        message = self._app.translate("mypycli.error.user_canceled")
                        self._app.console.warning(message)
                        return True
                    except Exception as e:
                        self._app.logger.exception(f"command failed: {result}")
                        message = self._app.translate("mypycli.error.command_failed", error=e)
                        self._app.console.error(message)
                        return True
                return True
            candidates = match.commands

        self._app.console.print_help(candidates)
        return True

    def _ensure_session(self) -> PromptSession[str]:
        if self._session is None:
            self._session = PromptSession(
                completer=self._build_completer(),
                complete_while_typing=False,
                history=self._app.history,
                style=Style.from_dict(
                    {
                        "completion-menu.completion": "noinherit",
                        "completion-menu.completion.current": "reverse",
                    }
                ),
            )
        return self._session

    def _build_completer(self) -> NestedCompleter:
        def _completer_children(item: Command | CommandGroup) -> dict[str, Any] | None:
            if isinstance(item, Command):
                return None
            return {sub.name: _completer_children(sub) for sub in item.commands}

        data = {cmd.name: _completer_children(cmd) for cmd in self._app.commands}
        return NestedCompleter.from_nested_dict(data)

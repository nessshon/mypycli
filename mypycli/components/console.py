from collections.abc import Callable, Sequence
from typing import Literal

from rich.console import Console as RichConsole
from rich.console import Group
from rich.padding import Padding
from rich.panel import Panel
from rich.progress import Progress, ProgressColumn
from rich.table import Table
from rich.text import Text

from mypycli.types import Command, CommandGroup


class Console(RichConsole):
    def info(self, message: str | Text) -> None:
        self.print(message, style="cyan")

    def success(self, message: str | Text) -> None:
        self.print(message, style="green")

    def warning(self, message: str | Text) -> None:
        self.print(message, style="yellow")

    def error(self, message: str | Text) -> None:
        self.print(message, style="red")

    def debug(self, message: str | Text) -> None:
        self.print(message, style="magenta")

    def note(self, message: str | Text) -> None:
        self.print(message, style="bright_black")

    def print_help(self, commands: list[Command | CommandGroup]) -> None:
        table = Table.grid(padding=(0, 2))
        table.add_column(no_wrap=True)
        table.add_column(style="dim", overflow="fold")
        table.add_column(overflow="fold")

        for cmd in commands:
            if isinstance(cmd, CommandGroup):
                table.add_row(f"▸ {cmd.name}", "", Text(cmd.description))
            else:
                table.add_row(f"  {cmd.name}", Text(cmd.usage), Text(cmd.description))

        self.print(table)

    def print_table(
        self,
        rows: Sequence[Sequence[str | Text]],
        header: str | Text | None = None,
        footer: str | Text | None = None,
        short_columns: Sequence[int] | None = None,
    ) -> None:
        if short_columns is None:
            short_columns = []

        headers, *data = rows
        table = Table(title=header, caption=footer, header_style="bold", border_style="dim", show_lines=True)
        for i, h in enumerate(headers, start=1):
            overflow: Literal["fold", "ellipsis"] = "ellipsis" if i in short_columns else "fold"
            table.add_column(h, overflow=overflow)
        for row in data:
            table.add_row(*row)

        self.print(table)

    def print_panel(
        self,
        body: Sequence[tuple[str | Text, str | Text]],
        short_column: bool = False,
        header: str | Text | None = None,
        footer: str | Text | None = None,
    ) -> None:
        overflow: Literal["fold", "ellipsis"] = "ellipsis" if short_column else "fold"

        table = Table.grid(padding=(0, 2), expand=True)
        table.add_column(no_wrap=True)
        table.add_column(ratio=1, overflow=overflow)

        for row in body:
            table.add_row(*row)
        group = Group(Text(""), Padding(table, (0, 2)), Text(""))
        panel = Panel(group, title=header, subtitle=footer, title_align="left", subtitle_align="right")

        self.print(panel)

    def progress_context(
        self,
        *columns: str | ProgressColumn,
        auto_refresh: bool = True,
        refresh_per_second: float = 10,
        speed_estimate_period: float = 30.0,
        transient: bool = False,
        redirect_stdout: bool = True,
        redirect_stderr: bool = True,
        get_time: Callable[[], float] | None = None,
        disable: bool = False,
        expand: bool = False,
    ) -> Progress:
        return Progress(
            *columns,
            console=self,
            auto_refresh=auto_refresh,
            refresh_per_second=refresh_per_second,
            speed_estimate_period=speed_estimate_period,
            transient=transient,
            redirect_stdout=redirect_stdout,
            redirect_stderr=redirect_stderr,
            get_time=get_time,
            disable=disable,
            expand=expand,
        )

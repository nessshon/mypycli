from __future__ import annotations

from mypycli.console.output import ConsoleOutput
from mypycli.types import Command


class TestCollectHelpLines:
    def test_collapsed_group_not_in_main_lines(self) -> None:
        """Collapsed groups are rendered by print_help directly, not via _collect_help_lines."""
        cmd = Command(
            "db",
            description="Manage database",
            children=[Command("show", lambda a, x: None, "Show")],
        )
        lines = ConsoleOutput._collect_help_lines([cmd], prefix="")
        assert lines == []

    def test_expanded_group_yields_children(self) -> None:
        cmd = Command(
            "db",
            description="Manage database",
            expand=True,
            children=[
                Command("show", lambda a, x: None, "Show full database"),
                Command("get", lambda a, x: None, "Get field"),
            ],
        )
        lines = ConsoleOutput._collect_help_lines([cmd], prefix="")
        names = [name for name, _, _ in lines]
        assert names == ["db show", "db get"]

    def test_leaf_command(self) -> None:
        cmd = Command("status", lambda a, x: None, "Show status")
        lines = ConsoleOutput._collect_help_lines([cmd], prefix="")
        assert lines == [("status", "", "Show status")]


class TestPrintHelp:
    def _render(self, commands: list[Command], capsys: object) -> str:
        ConsoleOutput.print_help(commands)
        captured = capsys.readouterr()  # type: ignore[attr-defined]
        return captured.out

    def test_regular_command_uses_leading_indent(self, capsys: object) -> None:
        out = self._render([Command("status", lambda a, x: None, "Show status")], capsys)
        assert out.startswith("  status")

    def test_collapsed_group_uses_hanging_marker(self, capsys: object) -> None:
        out = self._render(
            [
                Command(
                    "db",
                    description="Database commands",
                    children=[Command("show", lambda a, x: None, "Show")],
                ),
            ],
            capsys,
        )
        assert out.startswith("\u25b8 db")

    def test_mixed_preserves_registration_order(self, capsys: object) -> None:
        lines = self._render(
            [
                Command("register", lambda a, x: None, "Register"),
                Command(
                    "db",
                    description="Database commands",
                    children=[Command("show", lambda a, x: None, "Show")],
                ),
                Command("status", lambda a, x: None, "Show status"),
            ],
            capsys,
        ).splitlines()
        assert lines[0].lstrip().startswith("register")
        assert lines[1].startswith("\u25b8 db")
        assert lines[2].lstrip().startswith("status")

    def test_names_align_across_regular_and_group(self, capsys: object) -> None:
        out = self._render(
            [
                Command("status", lambda a, x: None, "Show"),
                Command(
                    "db",
                    description="Database",
                    children=[Command("show", lambda a, x: None, "Show")],
                ),
            ],
            capsys,
        ).splitlines()
        # "  status" — 'status' starts at col 2 (0-indexed)
        # "▸ db"    — 'db' starts at col 2 (0-indexed) after marker+space
        status_line = out[0]
        db_line = out[1]
        assert status_line.index("status") == db_line.index("db")

    def test_expanded_group_inlined(self, capsys: object) -> None:
        out = self._render(
            [
                Command(
                    "db",
                    description="Database commands",
                    expand=True,
                    children=[Command("get", lambda a, x: None, "Get", usage="<field>")],
                ),
            ],
            capsys,
        )
        # Name and usage are separately aligned columns now; both present on the line.
        assert "  db get" in out
        assert "<field>" in out

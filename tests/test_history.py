from pathlib import Path

from mypycli.components.history import History


class TestHistory:
    def test_append_string_via_prompt_toolkit_contract(self, tmp_path: Path) -> None:
        history = History(tmp_path, "app")
        history.append_string("first command")

        assert history.load_entries()[0].command == "first command"

    def test_limit_keeps_last_entries(self, tmp_path: Path) -> None:
        history = History(tmp_path, "app", limit=2)
        for i in range(4):
            history.store_string(f"cmd {i}")

        entries = history.load_entries()
        assert [e.command for e in entries] == ["cmd 2", "cmd 3"]

    def test_load_history_strings_newest_first(self, tmp_path: Path) -> None:
        history = History(tmp_path, "app")
        history.store_string("old")
        history.store_string("new")

        assert history.load_history_strings() == ["new", "old"]

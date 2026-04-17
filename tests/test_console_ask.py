from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from mypycli.console.console import Console
from mypycli.types import Confirm, Input, Multiselect, Secret, Select


def _make_console() -> Console:
    app = MagicMock()
    app.name = "test"
    app.label = "Test"
    return Console(app=app)


class TestConsoleAsk:
    def test_input_with_and_without_default(self) -> None:
        console = _make_console()
        with patch.object(console, "input", return_value="bob") as mock:
            assert console.ask(Input("Name", default="root")) == "bob"
        mock.assert_called_once_with("Name", default="root", validate=None)

        with patch.object(console, "input", return_value="val") as mock:
            console.ask(Input("Name"))
        mock.assert_called_once_with("Name", default=None, validate=None)

    def test_input_forwards_validate(self) -> None:
        def _validator(_: str) -> str | None:
            return None

        console = _make_console()
        with patch.object(console, "input", return_value="x") as mock:
            console.ask(Input("Name", validate=_validator))
        mock.assert_called_once_with("Name", default=None, validate=_validator)

    def test_secret(self) -> None:
        console = _make_console()
        with patch.object(console, "secret", return_value="s3cret") as mock:
            assert console.ask(Secret("Password")) == "s3cret"
        mock.assert_called_once_with("Password", validate=None)

    def test_secret_forwards_validate(self) -> None:
        def _validator(_: str) -> str | None:
            return None

        console = _make_console()
        with patch.object(console, "secret", return_value="x") as mock:
            console.ask(Secret("Password", validate=_validator))
        mock.assert_called_once_with("Password", validate=_validator)

    def test_confirm(self) -> None:
        console = _make_console()
        with patch.object(console, "confirm", return_value=True) as mock:
            assert console.ask(Confirm("Sure?", default=True)) is True
        mock.assert_called_once_with("Sure?", default=True)

    def test_select(self) -> None:
        console = _make_console()
        with patch.object(console, "select", return_value="b") as mock:
            assert console.ask(Select("Pick", ["a", "b", "c"])) == "b"
        mock.assert_called_once_with("Pick", ["a", "b", "c"])

    def test_multiselect(self) -> None:
        console = _make_console()
        with patch.object(console, "multiselect", return_value=["x"]) as mock:
            assert console.ask(Multiselect("Pick many", ["x", "y"])) == ["x"]
        mock.assert_called_once_with("Pick many", ["x", "y"])

    def test_unknown_type_raises(self) -> None:
        with pytest.raises(TypeError):
            _make_console().ask("not a question")  # type: ignore[arg-type]

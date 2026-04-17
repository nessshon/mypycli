from __future__ import annotations

import pytest
from pydantic import BaseModel

from mypycli.utils.errors import format_validation_error


class _M(BaseModel):
    n: int
    inner: dict[str, int] = {}


def test_passthrough_for_non_validation_error() -> None:
    assert format_validation_error(RuntimeError("plain")) == "plain"


def test_formats_validation_errors() -> None:
    with pytest.raises(Exception) as exc:
        _M(n="abc")  # type: ignore[arg-type]

    msg = format_validation_error(exc.value)
    assert "n" in msg
    assert ":" in msg


def test_joins_multiple_errors_with_semicolons() -> None:
    class Multi(BaseModel):
        a: int
        b: int

    with pytest.raises(Exception) as exc:
        Multi(a="x", b="y")  # type: ignore[arg-type]

    msg = format_validation_error(exc.value)
    assert "; " in msg
    assert "a" in msg and "b" in msg

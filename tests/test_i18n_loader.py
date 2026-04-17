from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from mypycli.i18n.loader import FlattenError, flatten, load_flat

if TYPE_CHECKING:
    from pathlib import Path


def test_flatten_nested_to_dotted() -> None:
    data = {"a": {"b": {"c": "x"}}, "y": "z"}
    assert flatten(data) == {"a.b.c": "x", "y": "z"}


def test_flatten_multiple_leaves() -> None:
    data = {"console": {"welcome": "hi", "goodbye": "bye"}}
    assert flatten(data) == {"console.welcome": "hi", "console.goodbye": "bye"}


def test_flatten_empty_dict() -> None:
    assert flatten({}) == {}


def test_flatten_leaf_then_branch_collision() -> None:
    # Leaf exists at "foo", then a branch under "foo" would conflict.
    # Simulated via existing pre-populated dict.
    with pytest.raises(FlattenError):
        flatten({"foo": {"bar": "baz"}}, existing={"foo": "leaf"})


def test_flatten_branch_then_leaf_collision() -> None:
    # Branch exists at "foo.x", then a leaf at "foo" would conflict.
    with pytest.raises(FlattenError):
        flatten({"foo": "leaf"}, existing={"foo.x": "y"})


def test_flatten_non_str_value() -> None:
    with pytest.raises(FlattenError):
        flatten({"a": 42})


def test_flatten_non_str_value_nested() -> None:
    with pytest.raises(FlattenError):
        flatten({"a": {"b": [1, 2]}})


def test_load_flat_yaml_boolean_key_rejected(tmp_path: Path) -> None:
    # YAML 1.1 treats unquoted `yes`/`no`/`on`/`off` as booleans. pyyaml turns such
    # keys into ``True``/``False`` which would silently produce a wrong catalog.
    p = tmp_path / "en.yml"
    p.write_text('table:\n  yes: "da"\n  no: "net"\n', encoding="utf-8")
    with pytest.raises(FlattenError) as exc_info:
        load_flat(p)
    assert "Non-string key" in str(exc_info.value)


def test_load_flat(tmp_path: Path) -> None:
    p = tmp_path / "en.yml"
    p.write_text('mypycli:\n  welcome: "hi"\n  goodbye: "bye"\n', encoding="utf-8")
    assert load_flat(p) == {"mypycli.welcome": "hi", "mypycli.goodbye": "bye"}


def test_load_flat_empty(tmp_path: Path) -> None:
    p = tmp_path / "en.yml"
    p.write_text("", encoding="utf-8")
    assert load_flat(p) == {}


def test_load_flat_invalid_yaml(tmp_path: Path) -> None:
    p = tmp_path / "en.yml"
    p.write_text("a: [1, 2\n  b: c", encoding="utf-8")
    with pytest.raises(FlattenError) as exc_info:
        load_flat(p)
    assert "Invalid YAML" in str(exc_info.value)


def test_load_flat_nonstring_value(tmp_path: Path) -> None:
    p = tmp_path / "en.yml"
    p.write_text("count: 42\n", encoding="utf-8")
    with pytest.raises(FlattenError):
        load_flat(p)


def test_load_flat_root_not_mapping(tmp_path: Path) -> None:
    p = tmp_path / "en.yml"
    p.write_text("- a\n- b\n", encoding="utf-8")
    with pytest.raises(FlattenError):
        load_flat(p)

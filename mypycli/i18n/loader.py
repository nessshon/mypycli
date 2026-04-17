from __future__ import annotations

from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from pathlib import Path


class FlattenError(ValueError):
    """Raised when a YAML catalog cannot be flattened (bad shape, key/value type, leaf/branch collision)."""


def flatten(
    data: dict[str, Any],
    *,
    existing: dict[str, str] | None = None,
    prefix: str = "",
) -> dict[str, str]:
    """Flatten a nested dict into a dotted-key flat dict of str values."""
    out: dict[str, str] = dict(existing or {})
    _walk(data, prefix, out)
    return out


def _walk(node: Any, prefix: str, out: dict[str, str]) -> None:
    if not isinstance(node, dict):
        raise FlattenError(f"Expected dict at '{prefix or '<root>'}', got {type(node).__name__}")
    for key, value in node.items():
        if not isinstance(key, str):
            raise FlattenError(
                f"Non-string key at '{prefix or '<root>'}': {key!r} ({type(key).__name__}); "
                f"quote YAML-reserved words like 'yes'/'no'/'on'/'off' explicitly"
            )
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            if path in out:
                raise FlattenError(f"Collision at '{path}': leaf and branch conflict")
            _walk(value, path, out)
        elif isinstance(value, str):
            prefix_marker = f"{path}."
            if any(k.startswith(prefix_marker) for k in out):
                raise FlattenError(f"Collision at '{path}': leaf and branch conflict")
            out[path] = value
        else:
            raise FlattenError(f"Non-string value at '{path}': {type(value).__name__}")


def load_flat(path: Path) -> dict[str, str]:
    """Parse a YAML file and return its flattened dotted-key dict."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise FlattenError(f"Invalid YAML in {path}: {exc}") from exc
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise FlattenError(f"Root of {path} must be a mapping, got {type(raw).__name__}")
    return flatten(raw)

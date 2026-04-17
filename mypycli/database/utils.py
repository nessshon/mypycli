from __future__ import annotations

import fcntl
import json
import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path


def read_json_locked(path: Path) -> dict[str, Any]:
    """Read a JSON object from ``path`` under a shared fcntl lock.

    :raises json.JSONDecodeError: If the file does not contain a JSON object.
    :raises OSError: If the file cannot be opened.
    """
    with open(path, encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_SH)
        try:
            result: dict[str, Any] = json.load(f)
            return result
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def write_json_locked(path: Path, data: dict[str, Any]) -> None:
    """Write ``data`` to ``path`` as indented JSON under an exclusive fcntl lock.

    The file is opened without truncation so the lock is acquired before any
    destructive operation; content is replaced atomically under the held lock
    and ``fsync``-ed before release so a successful call is durable on disk.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(exist_ok=True)
    with open(path, "r+", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.seek(0)
            f.truncate()
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def resolve_path(data: dict[str, Any], path: str) -> tuple[bool, Any]:
    """Resolve a dot-separated ``path`` against nested dict ``data``.

    :returns: ``(True, value)`` when the path resolves, ``(False, None)`` otherwise.
    """
    current: Any = data
    for key in path.split("."):
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return False, None
    return True, current


def assign_to_model(root: object, keys: list[str], value: Any) -> None:
    """Descend through attributes of ``root`` and ``setattr`` on the leaf.

    :raises KeyError: If an intermediate attribute is ``None``.
    """
    current: Any = root
    for key in keys[:-1]:
        current = getattr(current, key, None)
        if current is None:
            raise KeyError(".".join(keys))
    setattr(current, keys[-1], value)


def assign_to_dict(root: dict[str, Any], keys: list[str], value: Any) -> None:
    """Descend through dict keys of ``root`` and assign ``value`` at the leaf.

    :raises KeyError: If an intermediate key is missing or not a dict.
    """
    if len(keys) == 1:
        root[keys[0]] = value
        return
    extra = root.get(keys[0])
    if not isinstance(extra, dict):
        raise KeyError(".".join(keys))
    current = extra
    for key in keys[1:-1]:
        if not isinstance(current, dict) or key not in current:
            raise KeyError(".".join(keys))
        current = current[key]
    current[keys[-1]] = value

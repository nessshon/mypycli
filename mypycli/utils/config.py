from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def read_config(path: str | Path, model: type[T]) -> T:
    """Parse the JSON file at ``path`` into an instance of ``model``.

    :param path: JSON file to read.
    :param model: Pydantic ``BaseModel`` subclass to validate against.
    :raises FileNotFoundError: ``path`` does not exist.
    :raises pydantic.ValidationError: JSON does not match the model schema.
    :raises json.JSONDecodeError: File contents are not valid JSON.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return model.model_validate(data)


def write_config(path: str | Path, config: BaseModel) -> None:
    """Atomically write ``config`` as JSON to ``path``, preserving target mode and ownership.

    The payload is first written to ``<path>.tmp`` and then renamed onto the target.
    When the target already exists, its mode (e.g. ``0o600`` for secrets) is copied
    onto the temp file and ownership is best-effort mirrored; failures to ``chown``
    are suppressed so unprivileged writers can still update their own files.

    :param path: Destination JSON path; parent directories are created if missing.
    :param config: Pydantic model instance serialized via ``model_dump_json``.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f"{target.name}.tmp")
    tmp.write_text(config.model_dump_json(by_alias=True, indent=2) + "\n", encoding="utf-8")
    if target.exists():
        st = target.stat()
        os.chmod(tmp, st.st_mode)
        with contextlib.suppress(PermissionError):
            os.chown(tmp, st.st_uid, st.st_gid)
    tmp.replace(target)

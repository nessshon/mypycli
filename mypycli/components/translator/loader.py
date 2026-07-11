from pathlib import Path
from typing import Any

import yaml


def load_yaml(path: Path) -> dict[str, str]:
    return flatten_yaml(path.read_text(encoding="utf-8"), source=str(path))


def flatten_yaml(text: str, *, source: str) -> dict[str, str]:
    raw = yaml.safe_load(text)

    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"Root of {source} must be a mapping, got {type(raw).__name__}")

    return _flatten(raw)


def _flatten(data: dict[str, Any], prefix: str = "") -> dict[str, str]:
    result: dict[str, str] = {}

    for key, value in data.items():
        full_key = f"{prefix}.{key}" if prefix else key

        if isinstance(value, dict):
            nested = _flatten(value, prefix=full_key)
            result.update(nested)
        elif isinstance(value, str):
            result[full_key] = value
        else:
            raise ValueError(f"Locale value at '{full_key}' must be str or dict, got {type(value).__name__}")

    return result

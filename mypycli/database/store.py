from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any, Generic, TypeVar

from mypycli.database.schema import DatabaseSchema, _wire_model
from mypycli.database.utils import (
    assign_to_dict,
    assign_to_model,
    read_json_locked,
    resolve_path,
    write_json_locked,
)

T = TypeVar("T", bound=DatabaseSchema)


class Database(Generic[T]):
    """Typed JSON-file store with auto-save on mutation and mtime-based reloads."""

    def __init__(
        self,
        data_schema: type[T],
        path: str | Path,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        self._path = Path(path)
        self._data_schema = data_schema
        self._lock = threading.RLock()
        # ``modules`` is sourced from disk on demand, never cached in memory,
        # so concurrent writers can't clobber each other's sections.
        self._extras: dict[str, Any] = {}
        self._known_keys: set[str] = set()
        self._data: T = data_schema()
        self._last_mtime: float = 0.0
        self._logger = logger or logging.getLogger("mypycli.database")

    def __getattr__(self, name: str) -> Any:
        schema = object.__getattribute__(self, "_data_schema")
        if name in schema.model_fields:
            self._refresh_if_stale()
            return getattr(object.__getattribute__(self, "_data"), name)
        raise AttributeError(f"'{type(self).__name__}' has no attribute {name!r}")

    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith("_"):
            super().__setattr__(name, value)
            return
        try:
            schema = object.__getattribute__(self, "_data_schema")
        except AttributeError:
            super().__setattr__(name, value)
            return
        if name in schema.model_fields:
            setattr(object.__getattribute__(self, "_data"), name, value)
        else:
            super().__setattr__(name, value)

    @property
    def data(self) -> T:
        """Return the schema instance, reloading from disk if externally modified."""
        self._refresh_if_stale()
        return self._data

    @property
    def schema(self) -> type[T]:
        """Return the schema class."""
        return self._data_schema

    @property
    def path(self) -> Path:
        """Return the on-disk JSON path."""
        return self._path

    @property
    def is_loaded(self) -> bool:
        """Return ``True`` once ``load()`` has succeeded."""
        return self._last_mtime != 0.0

    @property
    def debug(self) -> bool:
        """Framework-owned debug flag persisted under the ``debug`` extras key."""
        return bool(self.get_extra("debug"))

    @debug.setter
    def debug(self, value: bool) -> None:
        self.set_extra("debug", bool(value))

    @property
    def language(self) -> str:
        """Framework-owned language code persisted under the ``language`` extras key."""
        return str(self.get_extra("language") or "")

    @language.setter
    def language(self, value: str) -> None:
        self.set_extra("language", str(value))

    def load(self, *, auto_create: bool = False) -> None:
        """Load JSON from disk; create with defaults when missing and ``auto_create``."""
        with self._lock:
            if self._path.exists():
                self._reload_locked()
                return
            if not auto_create:
                raise FileNotFoundError(self._path)
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._extras["debug"] = False
            self._extras["language"] = ""
            self._known_keys.add("debug")
            self._known_keys.add("language")
            write_json_locked(self._path, {**self._extras, **self._data.model_dump()})
            self._last_mtime = self._path.stat().st_mtime
            _wire_model(self._data, self.save)

    def save(self) -> None:
        """Persist ``_data`` and non-``modules`` extras; leaves ``modules`` untouched on disk."""
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            file_data = self._read_file_or_empty()
            preserved_modules = file_data.get("modules")
            foreign = {k: v for k, v in file_data.items() if k not in self._known_keys and k != "modules"}
            merged: dict[str, Any] = {
                **foreign,
                **{k: v for k, v in self._extras.items() if k != "modules"},
                **self._data.model_dump(),
            }
            if isinstance(preserved_modules, dict):
                merged["modules"] = preserved_modules
            write_json_locked(self._path, merged)
            self._last_mtime = self._path.stat().st_mtime

    def all_data(self) -> dict[str, Any]:
        """Return a merged snapshot of schema data, extras, and ``modules`` (read fresh)."""
        self._refresh_if_stale()
        with self._lock:
            result: dict[str, Any] = {**self._data.model_dump(), **self._extras}
            file_modules = self._read_file_or_empty().get("modules")
            if isinstance(file_modules, dict):
                result["modules"] = dict(file_modules)
            return result

    def get_extra(self, key: str) -> Any:
        """Return the extras value for ``key``, or ``None`` if absent."""
        self._refresh_if_stale()
        with self._lock:
            return self._extras.get(key)

    def set_extra(self, key: str, value: Any) -> None:
        """Store ``value`` under ``key`` in extras and persist."""
        with self._lock:
            self._extras[key] = value
            self._known_keys.add(key)
            self.save()

    def del_extra(self, key: str) -> None:
        """Remove the extras entry for ``key``; no-op if absent."""
        with self._lock:
            if key not in self._extras:
                return
            del self._extras[key]
            self.save()

    def get_module_data(self, module_name: str) -> dict[str, Any]:
        """Return a fresh-from-file copy of ``modules/<module_name>``, or ``{}`` if absent."""
        with self._lock:
            modules = self._read_file_or_empty().get("modules")
            if not isinstance(modules, dict):
                return {}
            section = modules.get(module_name)
            return dict(section) if isinstance(section, dict) else {}

    def set_module_data(self, module_name: str, data: dict[str, Any]) -> None:
        """Atomically replace ``modules/<module_name>``; preserves every other module."""
        with self._lock:
            file_data = self._read_file_or_empty()
            modules = file_data.get("modules")
            if not isinstance(modules, dict):
                modules = {}
                file_data["modules"] = modules
            modules[module_name] = data
            write_json_locked(self._path, file_data)
            self._last_mtime = self._path.stat().st_mtime

    def patch_module_data(self, module_name: str, changes: dict[str, Any]) -> None:
        """Atomically shallow-merge ``changes`` into ``modules/<module_name>``."""
        with self._lock:
            file_data = self._read_file_or_empty()
            modules = file_data.get("modules")
            if not isinstance(modules, dict):
                modules = {}
                file_data["modules"] = modules
            section = modules.get(module_name)
            if not isinstance(section, dict):
                section = {}
            section.update(changes)
            modules[module_name] = section
            write_json_locked(self._path, file_data)
            self._last_mtime = self._path.stat().st_mtime

    def del_module_data(self, module_name: str) -> None:
        """Remove persisted data for ``module_name``; drops ``modules`` when empty."""
        with self._lock:
            file_data = self._read_file_or_empty()
            modules = file_data.get("modules")
            if not isinstance(modules, dict) or module_name not in modules:
                return
            del modules[module_name]
            if not modules:
                del file_data["modules"]
            write_json_locked(self._path, file_data)
            self._last_mtime = self._path.stat().st_mtime

    def installed_modules(self) -> list[str]:
        """Return names of modules with persisted data (read fresh from disk)."""
        with self._lock:
            modules = self._read_file_or_empty().get("modules")
            return list(modules.keys()) if isinstance(modules, dict) else []

    def get_by_path(self, path: str) -> tuple[bool, Any]:
        """Resolve a dot-path across schema, extras, and modules; returns ``(found, value)``."""
        return resolve_path(self.all_data(), path)

    def set_by_path(self, path: str, value: Any) -> None:
        """Assign ``value`` at a dot-path; ``modules.*`` paths route through ``set_module_data``."""
        keys = path.split(".")
        top_key = keys[0]
        if top_key == "modules":
            if len(keys) < 3:
                raise KeyError(path)
            module_name = keys[1]
            section = self.get_module_data(module_name)
            if len(keys) == 3:
                section[keys[2]] = value
            else:
                assign_to_dict(section, keys[2:], value)
            self.set_module_data(module_name, section)
            return
        is_extras = False
        with self._lock:
            if hasattr(self._data, top_key):
                assign_to_model(self._data, keys, value)
            else:
                is_extras = True
                assign_to_dict(self._extras, keys, value)
                self._known_keys.add(top_key)
        if is_extras:
            self.save()

    def set_by_path_str(self, path: str, raw: str) -> None:
        """Assign at ``path``, parsing ``raw`` as JSON with bool-alias and string fallbacks."""
        lowered = raw.strip().lower()
        value: Any
        if lowered in ("true", "false"):
            value = lowered == "true"
        else:
            try:
                value = json.loads(raw)
            except json.JSONDecodeError:
                value = raw
        self.set_by_path(path, value)

    def _read_file_or_empty(self) -> dict[str, Any]:
        if not self._path.exists():
            return {}
        try:
            return read_json_locked(self._path)
        except json.JSONDecodeError:
            return {}

    def _refresh_if_stale(self) -> None:
        if self._last_mtime == 0.0:
            return
        try:
            mtime = self._path.stat().st_mtime
        except OSError:
            return
        if mtime == self._last_mtime:
            return
        with self._lock:
            try:
                mtime = self._path.stat().st_mtime
            except OSError:
                return
            if mtime == self._last_mtime:
                return
            self._reload_locked()

    def _reload_locked(self) -> None:
        try:
            raw = read_json_locked(self._path)
        except json.JSONDecodeError:
            self._logger.warning(f"Corrupt JSON in {self._path}, skipping reload")
            self._last_mtime = self._path.stat().st_mtime
            return
        known_fields = set(self._data_schema.model_fields.keys())
        self._known_keys = {k for k in raw if k != "modules"}
        known = {k: v for k, v in raw.items() if k in known_fields}
        self._extras = {k: v for k, v in raw.items() if k not in known_fields and k != "modules"}
        self._data = self._data_schema.model_validate(known)
        self._last_mtime = self._path.stat().st_mtime
        _wire_model(self._data, self.save)

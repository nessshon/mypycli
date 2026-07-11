import json
import os
import shutil
import tempfile
import threading
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager, suppress
from pathlib import Path
from typing import Generic, TypeVar

from filelock import FileLock
from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError

T = TypeVar("T", bound=BaseModel)


class JsonModel(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        extra="allow",
    )


class JsonFile(Generic[T]):
    def __init__(self, path: str | Path, model: type[T], *, create: bool = True):
        self.path = Path(path)
        self.model = model

        self._create = create
        self._tlock = threading.RLock()
        self._flock = FileLock(self.path.with_suffix(self.path.suffix + ".lock"))

        self._adapter = TypeAdapter(model)
        if create and not self.path.exists():
            with self._tlock, self._flock:
                if not self.path.exists():
                    self._save(model())

    def _load(self) -> T:
        try:
            raw = self.path.read_bytes()
        except FileNotFoundError:
            if self._create:
                return self.model()
            raise
        try:
            return self._adapter.validate_json(raw)
        except (ValidationError, json.JSONDecodeError):
            with suppress(OSError):
                shutil.copy2(self.path, self.path.with_name(f"{self.path.name}.corrupt"))
            return self.model()

    def _save(self, obj: T) -> None:
        raw = self._adapter.dump_json(obj, indent=2, by_alias=True)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(
            dir=self.path.parent,
            prefix=f".{self.path.name}.",
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(raw)
            with suppress(FileNotFoundError):
                st = self.path.stat()
                os.chmod(tmp, st.st_mode)
                with suppress(PermissionError):
                    os.chown(tmp, st.st_uid, st.st_gid)
            os.replace(tmp, self.path)
        except Exception:
            with suppress(OSError):
                os.unlink(tmp)
            raise

    @contextmanager
    def _transaction(self) -> Iterator[T]:
        with self._tlock, self._flock:
            obj = self._load()
            yield obj
            self._save(obj)

    def load(self) -> T:
        with self._tlock, self._flock:
            return self._load()

    def save(self, obj: T) -> None:
        with self._tlock, self._flock:
            self._save(obj)

    def transaction(self) -> AbstractContextManager[T]:
        return self._transaction()

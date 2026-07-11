import time
from pathlib import Path

from prompt_toolkit.history import History as PromptHistory
from pydantic import BaseModel, TypeAdapter, ValidationError


class _HistoryEntry(BaseModel):
    timestamp: float
    command: str


class History(PromptHistory):
    _ADAPTER = TypeAdapter(list[_HistoryEntry])

    def __init__(self, work_dir: str | Path, name: str, limit: int = 100) -> None:
        super().__init__()
        self._path = Path(f"{work_dir}/{name}.history")
        self._limit = limit

    def load_entries(self) -> list[_HistoryEntry]:
        if not self._path.exists():
            return []
        try:
            raw = self._path.read_text(encoding="utf-8")
            return self._ADAPTER.validate_json(raw)
        except (ValidationError, OSError):
            return []

    def store_string(self, string: str) -> None:
        entries = self.load_entries()
        entries.append(_HistoryEntry(timestamp=time.time(), command=string))
        data = self._ADAPTER.dump_json(entries[-self._limit :], indent=2)
        self._path.write_text(data.decode("utf-8"), encoding="utf-8")

    def load_history_strings(self) -> list[str]:
        return [e.command for e in reversed(self.load_entries())]

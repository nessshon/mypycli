from __future__ import annotations

import os
import stat
from typing import TYPE_CHECKING

import pytest
from pydantic import BaseModel, ValidationError

from mypycli.utils.config import read_config, write_config

if TYPE_CHECKING:
    from pathlib import Path


class _Sample(BaseModel):
    name: str
    count: int = 0


class TestWriteConfig:
    def test_roundtrip(self, tmp_path: Path) -> None:
        path = tmp_path / "config.json"
        write_config(path, _Sample(name="x", count=5))
        loaded = read_config(path, _Sample)
        assert loaded.name == "x"
        assert loaded.count == 5

    def test_no_tmp_file_after_success(self, tmp_path: Path) -> None:
        path = tmp_path / "config.json"
        write_config(path, _Sample(name="x"))
        assert path.exists()
        assert not path.with_name(f"{path.name}.tmp").exists()

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        path = tmp_path / "nested" / "dir" / "config.json"
        write_config(path, _Sample(name="x"))
        assert path.exists()

    def test_preserves_existing_mode(self, tmp_path: Path) -> None:
        path = tmp_path / "secret.json"
        write_config(path, _Sample(name="x"))
        os.chmod(path, 0o600)
        write_config(path, _Sample(name="y", count=7))
        assert stat.S_IMODE(path.stat().st_mode) == 0o600

    def test_output_ends_with_newline(self, tmp_path: Path) -> None:
        path = tmp_path / "config.json"
        write_config(path, _Sample(name="x"))
        assert path.read_text(encoding="utf-8").endswith("\n")


class TestReadConfig:
    def test_raises_for_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            read_config(tmp_path / "missing.json", _Sample)

    def test_validation_error_on_wrong_schema(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.json"
        path.write_text('{"count": "not-an-int"}', encoding="utf-8")
        with pytest.raises(ValidationError):
            read_config(path, _Sample)

    def test_uses_pydantic_defaults(self, tmp_path: Path) -> None:
        path = tmp_path / "defaults.json"
        path.write_text('{"name": "n"}', encoding="utf-8")
        loaded = read_config(path, _Sample)
        assert loaded.name == "n"
        assert loaded.count == 0

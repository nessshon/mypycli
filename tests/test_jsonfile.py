import multiprocessing
import os
import stat
import threading
from pathlib import Path

import pytest
from pydantic import BaseModel

from mypycli.utils.jsonfile import JsonFile


class Config(BaseModel):
    value: int = 0


def _bump(path: Path, times: int) -> None:
    store = JsonFile(path, Config)
    for _ in range(times):
        with store.transaction() as cfg:
            cfg.value += 1


def test_create_false_does_not_create(tmp_path: Path) -> None:
    store = JsonFile(tmp_path / "external.json", Config, create=False)

    assert not store.path.exists()
    with pytest.raises(FileNotFoundError):
        store.load()


def test_save_preserves_mode(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text('{"value": 1}')
    os.chmod(path, 0o640)

    JsonFile(path, Config).save(Config(value=2))

    assert stat.S_IMODE(path.stat().st_mode) == 0o640


def test_corrupt_file_backed_up(tmp_path: Path) -> None:
    path = tmp_path / "db.json"
    path.write_text("{broken json")

    assert JsonFile(path, Config).load() == Config()
    assert (tmp_path / "db.json.corrupt").read_text() == "{broken json"


def test_transaction_roundtrip(tmp_path: Path) -> None:
    store = JsonFile(tmp_path / "db.json", Config)
    with store.transaction() as cfg:
        cfg.value = 42

    assert store.load().value == 42


def test_concurrent_threads(tmp_path: Path) -> None:
    path = tmp_path / "db.json"
    threads = [threading.Thread(target=_bump, args=(path, 10)) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert JsonFile(path, Config).load().value == 50


def test_concurrent_processes(tmp_path: Path) -> None:
    path = tmp_path / "db.json"
    processes = [multiprocessing.Process(target=_bump, args=(path, 10)) for _ in range(4)]
    for p in processes:
        p.start()
    for p in processes:
        p.join()

    assert JsonFile(path, Config).load().value == 40

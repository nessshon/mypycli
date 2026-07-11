from pathlib import Path

import pytest

from mypycli.__main__ import main


def test_init_copies_locales(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["mypycli", "init"])

    main()

    assert (tmp_path / "locales" / "en.yml").is_file()
    assert (tmp_path / "locales" / "ru.yml").is_file()


def test_init_fails_if_locales_exists(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["mypycli", "init"])
    Path(tmp_path / "locales").mkdir()

    with pytest.raises(SystemExit, match="1"):
        main()


def test_init_usage_on_unknown_args(monkeypatch):
    monkeypatch.setattr("sys.argv", ["mypycli"])

    with pytest.raises(SystemExit, match="2"):
        main()

from __future__ import annotations

from typing import TYPE_CHECKING

import yaml

from mypycli.cli.commands.locales import cmd_init

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_cli_entrypoint_init(tmp_path: Path) -> None:
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "mypycli.cli.standalone", "locales", "init"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "locales" / "en.yml").is_file()
    assert (tmp_path / "locales" / "ru.yml").is_file()
    assert (tmp_path / "locales" / "zh.yml").is_file()


def test_init_creates_user_locales(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    exit_code = cmd_init()
    assert exit_code == 0
    assert (tmp_path / "locales" / "en.yml").is_file()
    assert (tmp_path / "locales" / "ru.yml").is_file()
    assert (tmp_path / "locales" / "zh.yml").is_file()
    data = yaml.safe_load((tmp_path / "locales" / "en.yml").read_text())
    assert "mypycli" in data


def test_init_skips_existing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "locales").mkdir()
    (tmp_path / "locales" / "en.yml").write_text(
        'mypycli:\n  existing: "keep me"\nuser: {}\n', encoding="utf-8"
    )
    exit_code = cmd_init()
    assert exit_code == 0
    content = (tmp_path / "locales" / "en.yml").read_text()
    assert "keep me" in content


def test_sync_replaces_mypycli_section_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mypycli.cli.commands.locales import cmd_sync
    monkeypatch.chdir(tmp_path)
    (tmp_path / "locales").mkdir()
    (tmp_path / "locales" / "en.yml").write_text(
        'mypycli:\n  stale: "old value"\n'
        'dashboard:\n  title: "My Dashboard"\n',
        encoding="utf-8",
    )
    exit_code = cmd_sync()
    assert exit_code == 0
    data = yaml.safe_load((tmp_path / "locales" / "en.yml").read_text())
    assert "stale" not in (data.get("mypycli") or {})
    assert data["dashboard"]["title"] == "My Dashboard"


def test_sync_warns_when_no_library_counterpart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from mypycli.cli.commands.locales import cmd_sync
    monkeypatch.chdir(tmp_path)
    (tmp_path / "locales").mkdir()
    (tmp_path / "locales" / "fr.yml").write_text(
        'mypycli: {}\ndashboard:\n  title: "Tableau"\n',
        encoding="utf-8",
    )
    exit_code = cmd_sync()
    assert exit_code == 0
    captured = capsys.readouterr().out
    assert "fr" in captured
    assert "skip" in captured.lower() or "no library counterpart" in captured.lower()
    data = yaml.safe_load((tmp_path / "locales" / "fr.yml").read_text())
    assert data["dashboard"]["title"] == "Tableau"


def test_sync_missing_locales_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mypycli.cli.commands.locales import cmd_sync
    monkeypatch.chdir(tmp_path)
    exit_code = cmd_sync()
    assert exit_code == 1


def test_check_clean(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from mypycli.cli.commands.locales import cmd_check, cmd_init
    monkeypatch.chdir(tmp_path)
    cmd_init()
    assert cmd_check() == 0


def test_check_fails_when_mypycli_out_of_sync(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mypycli.cli.commands.locales import cmd_check
    monkeypatch.chdir(tmp_path)
    (tmp_path / "locales").mkdir()
    # Put a key in user's file that doesn't exist in library's en:
    (tmp_path / "locales" / "en.yml").write_text(
        'mypycli:\n  bogus_key_never_in_library: "x"\n',
        encoding="utf-8",
    )
    assert cmd_check() == 1


def test_check_fails_when_user_keys_differ(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mypycli.cli.commands.locales import cmd_check, cmd_init
    monkeypatch.chdir(tmp_path)
    cmd_init()
    # Add a user key to en but not to ru/zh:
    en = tmp_path / "locales" / "en.yml"
    data = yaml.safe_load(en.read_text()) or {}
    data["dashboard"] = {"title": "x"}
    en.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    assert cmd_check() == 1


def test_check_skips_mypycli_for_extra_language(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mypycli.cli.commands.locales import cmd_check
    monkeypatch.chdir(tmp_path)
    (tmp_path / "locales").mkdir()
    (tmp_path / "locales" / "fr.yml").write_text(
        "mypycli: {}\n", encoding="utf-8"
    )
    # Single language, no user keys → consistent by definition
    assert cmd_check() == 0


def test_check_missing_locales_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mypycli.cli.commands.locales import cmd_check
    monkeypatch.chdir(tmp_path)
    assert cmd_check() == 1

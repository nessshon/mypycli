from __future__ import annotations

import os
import re
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator
    from pathlib import Path
    from typing import TextIO

    from mypycli.application import Application


_LEVEL_NUM = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}
_LINE_RE = re.compile(r"^\[(\w+)\s*\]\s+\S+\s+\S+\s+<[^>]+>\s+(\S+):\s")


def run_logs(
    app: Application[Any],
    *,
    lines: int = 50,
    follow: bool = False,
    level: str | None = None,
    module: str | None = None,
    include_rotated: bool = False,
) -> None:
    """Print the tail of the application log file with optional follow, level and module filters.

    :param app: Application whose ``work_dir`` and ``name`` locate the log file.
    :param lines: Number of trailing lines to show after filtering.
    :param follow: Continue printing new lines as they are appended; exits on ``Ctrl+C``.
    :param level: Minimum level name (``DEBUG`` .. ``CRITICAL``); lower-level lines are dropped.
    :param module: Logger-name suffix filter; keeps records whose logger ``name`` equals or ends with ``.<module>``.
    :param include_rotated: Prepend rotated ``.N`` backups (oldest first) before the current log.
    """
    log_path = app.log_path
    if not log_path.exists():
        print("No log file yet")
        return

    threshold = _LEVEL_NUM[level] if level else None
    collected = _read_log_lines(log_path, include_rotated)
    filtered = list(_filter_log_stream(collected, threshold, module))
    for line in filtered[-lines:]:
        print(line.rstrip())

    if follow:
        _follow_log(log_path, threshold, module)


def _read_log_lines(path: Path, include_rotated: bool) -> list[str]:
    """Return log lines in chronological order; ``include_rotated`` prepends .N backups (highest N first).

    :param path: Current log file to read.
    :param include_rotated: When true, prepend ``.N`` rotated backups starting from the highest ``N``.
    """
    lines: list[str] = []
    if include_rotated:
        for i in range(9, 0, -1):
            backup = path.parent / f"{path.name}.{i}"
            if backup.exists():
                with open(backup, encoding="utf-8", errors="replace") as f:
                    lines.extend(f.readlines())
    with open(path, encoding="utf-8", errors="replace") as f:
        lines.extend(f.readlines())
    return lines


def _match_module(name: str, suffix: str) -> bool:
    """Return True when logger ``name`` equals ``suffix`` or ends with ``.<suffix>``.

    :param name: Logger name parsed from a log record.
    :param suffix: Suffix to match against ``name``.
    """
    return name == suffix or name.endswith(f".{suffix}")


def _line_passes(line: str, level_threshold: int | None, module_suffix: str | None, prev_keep: bool) -> bool:
    """Decide whether ``line`` passes the filters; multi-line records inherit ``prev_keep``.

    :param line: Raw log line to inspect.
    :param level_threshold: Minimum numeric level required; ``None`` disables level filtering.
    :param module_suffix: Logger-name suffix to match; ``None`` disables module filtering.
    :param prev_keep: Decision carried over when ``line`` does not start a new record.
    """
    m = _LINE_RE.match(line)
    if not m:
        return prev_keep
    level_ok = level_threshold is None or _LEVEL_NUM.get(m.group(1), 0) >= level_threshold
    module_ok = module_suffix is None or _match_module(m.group(2), module_suffix)
    return bool(level_ok and module_ok)


def _filter_log_stream(
    lines: Iterable[str],
    level_threshold: int | None,
    module_suffix: str | None,
) -> Iterator[str]:
    """Yield lines passing the level/module filters; multi-line records inherit the last seen decision.

    :param lines: Source iterable of raw log lines.
    :param level_threshold: Minimum numeric level required; ``None`` disables level filtering.
    :param module_suffix: Logger-name suffix to match; ``None`` disables module filtering.
    """
    keep = True
    for line in lines:
        keep = _line_passes(line, level_threshold, module_suffix, keep)
        if keep:
            yield line


def _follow_log(log_path: Path, level_threshold: int | None, module_suffix: str | None) -> None:
    """Tail ``log_path``, printing new lines as they appear; detects file rotation via inode change.

    :param log_path: Path to the active log file.
    :param level_threshold: Minimum numeric level required; ``None`` disables level filtering.
    :param module_suffix: Logger-name suffix to match; ``None`` disables module filtering.
    """
    try:
        _follow_loop(log_path, level_threshold, module_suffix)
    except KeyboardInterrupt:
        print()


def _follow_loop(log_path: Path, level_threshold: int | None, module_suffix: str | None) -> None:
    """Follow ``log_path`` forever; re-opens the file on rotation without growing the stack.

    :param log_path: Path to the active log file.
    :param level_threshold: Minimum numeric level required; ``None`` disables level filtering.
    :param module_suffix: Logger-name suffix to match; ``None`` disables module filtering.
    """
    keep = True
    while True:
        with open(log_path, encoding="utf-8", errors="replace") as f:
            f.seek(0, os.SEEK_END)
            while True:
                line = f.readline()
                if line:
                    keep = _line_passes(line, level_threshold, module_suffix, keep)
                    if keep:
                        print(line.rstrip())
                    continue
                time.sleep(0.2)
                if _rotated(f, log_path):
                    break


def _rotated(f: TextIO, log_path: Path) -> bool:
    """Return True when the open file's inode differs from ``log_path`` on disk (rotation happened).

    :param f: Currently open log file handle.
    :param log_path: Path to the active log file on disk.
    """
    try:
        return os.fstat(f.fileno()).st_ino != os.stat(log_path).st_ino
    except OSError:
        return False

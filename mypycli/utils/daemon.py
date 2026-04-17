from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def read_pid(pid_path: Path) -> int | None:
    """Read and parse the integer pid from ``pid_path``.

    :param pid_path: Path to the pid file.
    :returns: Parsed pid, or ``None`` when the file is missing or its contents are not a valid integer.
    """
    try:
        return int(pid_path.read_text().strip())
    except (FileNotFoundError, ValueError, OSError):
        return None


def is_alive(pid: int) -> bool | None:
    """Probe whether a process with ``pid`` exists.

    :param pid: Process id to probe.
    :returns: ``True`` if the process is alive, ``False`` if it is gone, ``None`` when it exists
        but belongs to a different user (``EPERM`` on signal 0).
    """
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return None
    return True

from __future__ import annotations

import functools
import os
import shlex
import shutil
import subprocess
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path


def run(
    args: Sequence[str | Path],
    *,
    capture: bool = True,
    timeout: float | None = 30,
    cwd: str | Path | None = None,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run an external command synchronously in text mode and return the completed process.

    :param args: Command and arguments. ``str`` and ``Path`` entries pass through
        to ``subprocess`` as-is (no coercion); anything else raises ``TypeError``.
    :param capture: Capture stdout/stderr when ``True``; inherit parent streams otherwise.
    :param timeout: Wall-clock timeout in seconds; ``None`` disables it. Defaults to 30.
    :param cwd: Working directory; ``None`` inherits.
    :param check: Raise ``CalledProcessError`` on a non-zero exit code.
    """
    return subprocess.run(
        args,
        capture_output=capture,
        text=True,
        timeout=timeout,
        cwd=cwd,
        check=check,
    )


def is_root() -> bool:
    """Whether the current effective UID is 0."""
    return os.geteuid() == 0


def is_tty() -> bool:
    """Whether both stdin and stdout are attached to an interactive terminal."""
    return sys.stdin.isatty() and sys.stdout.isatty()


def run_as_root(
    args: Sequence[str | Path],
    *,
    capture: bool = False,
    timeout: float | None = None,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run a command with root privileges, wrapping with ``sudo`` or ``su -c`` when not already root.

    :param args: Command and arguments; same rules as ``run``.
    :param capture: Capture stdout/stderr when ``True``.
    :param timeout: Wall-clock timeout in seconds; ``None`` disables it.
    :param check: Raise ``CalledProcessError`` on a non-zero exit code. The
        error's ``cmd`` is the original ``args`` — without any ``sudo``/``su``
        wrapping — so callers see the command they asked for.
    :raises RuntimeError: Escalation needed but neither ``sudo`` nor ``su`` is on PATH.
    """
    if is_root():
        return run(args, capture=capture, timeout=timeout, check=check)

    root_cmd = _find_root_cmd()
    if root_cmd == "su":
        wrapped: list[str | Path] = ["su", "-c", shlex.join(str(a) for a in args)]
    else:
        wrapped = [root_cmd, *args]

    result = run(wrapped, capture=capture, timeout=timeout)
    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(
            returncode=result.returncode,
            cmd=list(args),
            output=result.stdout,
            stderr=result.stderr,
        )
    return result


@functools.lru_cache(maxsize=1)
def _find_root_cmd() -> str:
    """Return ``"sudo"`` or ``"su"``, whichever is found first on PATH; cached for the process lifetime.

    :raises RuntimeError: If neither ``sudo`` nor ``su`` is available.
    """
    for tool in ("sudo", "su"):
        if shutil.which(tool):
            return tool
    raise RuntimeError("Root access required but no sudo or su found")

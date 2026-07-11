import functools
import locale
import os
import platform
import shlex
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from mypycli.types import DEFAULT_LANGUAGE_CODE, SUPPORTED_LANGUAGE_CODES


def is_root() -> bool:
    return os.geteuid() == 0


@functools.cache
def find_root_tool() -> Literal["sudo", "su"]:
    psys = platform.system()
    if psys not in ("Linux", "Darwin"):
        raise RuntimeError(f"find_root_tool: unsupported platform: {psys}")

    if shutil.which("sudo"):
        return "sudo"
    if shutil.which("su"):
        return "su"

    raise RuntimeError("find_root_tool: no sudo/su found")


def run(
    args: Sequence[str | Path | None],
    *,
    capture: bool = True,
    timeout: float | None = 30,
    cwd: str | Path | None = None,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(a) for a in args if a is not None],
        capture_output=capture,
        text=True,
        timeout=timeout,
        cwd=cwd,
        check=check,
    )


def run_as_root(
    args: Sequence[str | Path | None],
    *,
    capture: bool = False,
    timeout: float | None = 120,
    cwd: str | Path | None = None,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    normalized_args = [str(a) for a in args if a is not None]

    if is_root():
        cmd_args = normalized_args
    else:
        root_tool = find_root_tool()
        if root_tool == "sudo":
            cmd_args = [root_tool, "--", *normalized_args]
        else:
            cmd_args = [root_tool, "-c", shlex.join(normalized_args)]

    return run(cmd_args, capture=capture, timeout=timeout, cwd=cwd, check=check)


def system_language() -> str:
    lang_code, _enc = locale.getlocale()
    if not lang_code:
        return DEFAULT_LANGUAGE_CODE

    prefix = lang_code.split("_", 1)[0].lower()
    if prefix in SUPPORTED_LANGUAGE_CODES:
        return prefix

    return DEFAULT_LANGUAGE_CODE

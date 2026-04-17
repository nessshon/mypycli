from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any

from mypycli.modules.interfaces.installable import Installable

if TYPE_CHECKING:
    from mypycli.application import Application


def exit_with_failures(action: str, failed: list[tuple[str, Exception]]) -> None:
    """Print per-module failures to stderr and exit 1; no-op when ``failed`` is empty.

    :param action: Action verb for the message (``"Install"``, ``"Uninstall"``, ``"Update"``).
    :param failed: Pairs of module name and exception from per-module error collection.
    """
    if not failed:
        return
    for name, err in failed:
        print(f"{action} failed for {name}: {err}", file=sys.stderr)
    raise SystemExit(1)


def require_install(app: Application[Any]) -> None:
    """Exit with a clear message if any mandatory Installable module is not installed.

    Called by runtime commands (``daemon``, ``console``, ``update``) after ``app.start()``
    to prevent operating on a partially-set-up application.

    :raises SystemExit: If at least one mandatory Installable module has no DB entry.
    """
    installed = set(app.db.installed_modules())
    missing = [
        m.name
        for m in app.modules.by_interface(Installable, enabled_only=False)
        if m.mandatory and m.name not in installed
    ]
    if not missing:
        return
    print(f"{app.name}: required modules not installed: {', '.join(missing)}", file=sys.stderr)
    print(f"Run '{app.name} install' first.", file=sys.stderr)
    raise SystemExit(1)

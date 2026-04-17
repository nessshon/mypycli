from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING, Any

from mypycli.modules.interfaces.installable import Installable

if TYPE_CHECKING:
    from mypycli.application import Application


def select_install_modules(app: Application[Any]) -> list[str]:
    """Resolve the set of optional modules to install.

    When ``app.env_prefix`` is set and ``<PREFIX>_MODULES`` is a non-empty CSV, the
    list is parsed from the variable; unknown names raise ``RuntimeError`` and
    mandatory or already-installed names are silently dropped. Otherwise, on a TTY
    the user is prompted with an interactive multiselect; on non-TTY nothing is
    selected and ``[]`` is returned.

    :raises RuntimeError: The env variable references unknown module names.
    """
    if app.env_prefix is not None:
        env_var = f"{app.env_prefix}_MODULES"
        raw = os.environ.get(env_var)
        if raw is not None and raw.strip():
            return _resolve_env_modules(app, raw, env_var)

    installed = set(app.db.installed_modules())
    optional = [
        m.name
        for m in app.modules.by_interface(Installable, enabled_only=False)
        if not m.mandatory and m.name not in installed
    ]
    if not optional or not sys.stdin.isatty():
        return []
    return list(app.console.multiselect("Select modules to install:", choices=list(optional)))


def _resolve_env_modules(app: Application[Any], raw: str, env_var: str) -> list[str]:
    """Parse ``raw`` as a CSV of module names and filter against the registry.

    Mandatory and already-installed names are silently dropped (mandatory modules
    install regardless; installed ones are a no-op). Unknown names raise.
    """
    requested = [n.strip() for n in raw.split(",") if n.strip()]

    installables = app.modules.by_interface(Installable, enabled_only=False)
    all_names = {m.name for m in installables}
    mandatory_names = {m.name for m in installables if m.mandatory}
    installed_names = set(app.db.installed_modules())
    optional_available = sorted(m.name for m in installables if not m.mandatory and m.name not in installed_names)

    selected: list[str] = []
    unknown: list[str] = []
    for name in requested:
        if name not in all_names:
            unknown.append(name)
        elif name in mandatory_names or name in installed_names:
            continue
        else:
            selected.append(name)

    available = ", ".join(optional_available) if optional_available else "(none)"
    if unknown:
        raise RuntimeError(
            f"Unknown module(s) in {env_var}: {', '.join(sorted(set(unknown)))}. "
            f"Available optional modules: {available}"
        )
    return selected


def run_install(app: Application[Any], *, selected: list[str] | None = None) -> None:
    """Install mandatory modules plus optional ones in ``selected``.

    Each module's ``on_install`` owns its flow end to end: prompting the user via
    ``self.app.console``, provisioning resources, and persisting state via ``self.db``.
    The framework only decides the target set (mandatory + selected) and stops on
    the first failure so dependent modules do not run against a broken base.

    :param selected: Chosen optional module names, or ``None`` to prompt via
        interactive multiselect.
    :raises SystemExit: If a module's ``on_install`` raises.
    """
    app.start()
    try:
        if selected is None:
            selected = select_install_modules(app)

        chosen = set(selected)
        targets = [
            m for m in app.modules.by_interface(Installable, enabled_only=False) if m.mandatory or m.name in chosen
        ]

        for module in targets:
            try:
                module.on_install()
            except Exception as exc:
                app.logger.exception(f"Install failed: {module.name}")
                print(f"Install failed for {module.name}: {exc}", file=sys.stderr)
                raise SystemExit(1) from exc
            if module.name not in app.db.installed_modules():
                app.db.set_module_data(module.name, {})
    finally:
        app.stop()

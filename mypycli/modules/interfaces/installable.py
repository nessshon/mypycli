from __future__ import annotations

from abc import ABC, abstractmethod

from mypycli.modules.base import Module


class Installable(Module, ABC):
    """Interface for modules with install/uninstall lifecycle.

    Modules own the full install flow: prompt via ``self.app.console`` when a TTY
    is available, read env vars or config files for non-interactive runs, write
    state via ``self.db``. Other modules' data is available through the registry:
    ``self.app.modules.get_by_class(Other).db.<field>``.
    """

    @abstractmethod
    def on_install(self) -> None:
        """Install the module: gather inputs, provision resources, persist state."""

    @abstractmethod
    def on_uninstall(self) -> None:
        """Uninstall the module: remove services, files, and persisted data."""

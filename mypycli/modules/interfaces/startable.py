from __future__ import annotations

from abc import ABC, abstractmethod

from mypycli.modules.base import Module


class Startable(Module, ABC):
    """Console (REPL) session lifecycle hooks.

    Fires on REPL entry/exit only. Daemon modules do their setup inside
    ``on_daemon`` and register background work via ``run_task`` / ``run_cycle``.
    Use Startable for session-scoped resources that support interactive commands
    and status (e.g. network clients opened at REPL entry, closed at exit).
    """

    @abstractmethod
    def on_start(self) -> None:
        """Acquire session-scoped resources (network clients, caches, etc.)."""

    @abstractmethod
    def on_stop(self) -> None:
        """Release the resources acquired in ``on_start``."""

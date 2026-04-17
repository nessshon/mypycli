from __future__ import annotations

from abc import ABC, abstractmethod

from mypycli.modules.base import Module


class Daemonic(Module, ABC):
    """Interface for modules that run background tasks in daemon mode."""

    @abstractmethod
    def on_daemon(self) -> None:
        """Register background workers with ``self.app.worker`` when the app enters daemon mode."""

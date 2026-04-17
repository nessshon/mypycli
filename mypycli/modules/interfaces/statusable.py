from __future__ import annotations

from abc import ABC, abstractmethod

from mypycli.modules.base import Module


class Statusable(Module, ABC):
    """Interface for modules that can report runtime status to the console."""

    @abstractmethod
    def show_status(self) -> None:
        """Render the current module status to the console."""

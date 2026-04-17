from __future__ import annotations

from abc import ABC, abstractmethod

from mypycli.modules.base import Module


class Updatable(Module, ABC):
    """Interface for modules that can apply their own updates.

    ``on_update`` is responsible for detecting whether work is needed and
    reporting progress; the framework just invokes it on every Updatable module.
    """

    @property
    @abstractmethod
    def version(self) -> str:
        """Return the module's currently installed version/ref as a free-form string."""

    @abstractmethod
    def on_update(self) -> None:
        """Apply the update using module-specific logic; no-op if already up-to-date."""

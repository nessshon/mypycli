from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from mypycli.modules.base import Module

if TYPE_CHECKING:
    from mypycli.types import Command


class Commandable(Module, ABC):
    """Interface for modules that contribute commands to the console."""

    @abstractmethod
    def get_commands(self) -> list[Command]:
        """Return the commands this module exposes to the console.

        :returns: Commands to register in the console dispatcher.
        """

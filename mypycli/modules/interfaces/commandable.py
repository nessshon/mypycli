from abc import abstractmethod

from mypycli.modules import Module
from mypycli.types import Command, CommandGroup


class Commandable(Module):
    @property
    @abstractmethod
    def commands(self) -> list[Command | CommandGroup]: ...

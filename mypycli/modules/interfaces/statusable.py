from abc import abstractmethod

from mypycli.modules import Module


class Statusable(Module):
    @abstractmethod
    def print_status(self) -> None: ...

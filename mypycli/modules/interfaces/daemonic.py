from abc import abstractmethod

from mypycli.modules import Module


class Daemonic(Module):
    @abstractmethod
    def on_daemon(self) -> None: ...

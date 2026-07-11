from abc import abstractmethod

from mypycli.modules import Module


class Startable(Module):
    @abstractmethod
    def on_start(self) -> None: ...

    @abstractmethod
    def on_stop(self) -> None: ...

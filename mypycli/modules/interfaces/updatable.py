from abc import abstractmethod

from mypycli.modules import Module


class Updatable(Module):
    @property
    @abstractmethod
    def version(self) -> str: ...

    @abstractmethod
    def on_update(self) -> None: ...

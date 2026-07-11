from abc import abstractmethod

from mypycli.modules import Module


class Installable(Module):
    @abstractmethod
    def on_install(self) -> None: ...

    @abstractmethod
    def on_uninstall(self) -> None: ...

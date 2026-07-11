from typing import TypeVar

from mypycli.modules import Module

T = TypeVar("T")


class ModuleRegistry:
    def __init__(self) -> None:
        self._modules: dict[str, Module] = {}

    def register(self, module: Module) -> None:
        if module.name in self._modules:
            raise ValueError(f"Duplicate module name: {module.name}")
        self._modules[module.name] = module

    def get_all(self, *, enabled_only: bool = True) -> list[Module]:
        if enabled_only:
            return [m for m in self._modules.values() if m.is_enabled]
        return list(self._modules.values())

    def get_by_class(self, cls: type[T]) -> T:
        for module in self._modules.values():
            if isinstance(module, cls):
                return module
        raise KeyError(f"No module of type {cls.__name__}")

    def get_by_interface(self, interface: type[T], *, enabled_only: bool = True) -> list[T]:
        source: list[Module] = list(self._modules.values())
        if enabled_only:
            source = [m for m in source if m.is_enabled]
        return [m for m in source if isinstance(m, interface)]

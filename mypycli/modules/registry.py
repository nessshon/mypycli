from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from mypycli.application import Application
    from mypycli.modules.base import Module

T = TypeVar("T")


class ModuleRegistry:
    """Registry of module instances with typed lookups by name, class, and interface."""

    def __init__(self) -> None:
        self._modules: dict[str, Module] = {}

    def register(self, module: Module) -> None:
        """Add a module instance to the registry.

        :param module: Module to register, keyed by its ``name``.
        :raises ValueError: If a module with the same name is already registered.
        """
        if module.name in self._modules:
            raise ValueError(f"Duplicate module name: {module.name!r}")
        self._modules[module.name] = module

    def get(self, name: str) -> Module:
        """Look up a module by its ``name``.

        :param name: Module name to resolve.
        :returns: Registered module instance.
        :raises KeyError: If no module with this name is registered.
        """
        return self._modules[name]

    def get_by_class(self, cls: type[T]) -> T:
        """Return the first registered module that is an instance of ``cls``.

        :param cls: Concrete module class to match.
        :returns: Matching module instance.
        :raises KeyError: If no registered module is an instance of ``cls``.
        """
        for module in self._modules.values():
            if isinstance(module, cls):
                return module
        raise KeyError(f"No module of type {cls.__name__}")

    def all(self, *, enabled_only: bool = True) -> list[Module]:
        """Return all registered modules.

        :param enabled_only: When ``True``, skip modules whose ``is_enabled`` is false.
        :returns: List of modules in registration order.
        """
        if enabled_only:
            return [m for m in self._modules.values() if m.is_enabled]
        return list(self._modules.values())

    def by_interface(self, interface: type[T], *, enabled_only: bool = True) -> list[T]:
        """Return modules implementing ``interface``, in registration order.

        :param interface: Interface class to match via ``isinstance``.
        :param enabled_only: When ``True`` (default), skip modules whose ``is_enabled``
            is false. Pass ``False`` from the install flow to see all candidates.
        """
        source: list[Module] = list(self._modules.values())
        if enabled_only:
            source = [m for m in source if m.is_enabled]
        return [m for m in source if isinstance(m, interface)]


def build_modules(app: Application[Any], module_classes: list[type[Module]]) -> ModuleRegistry:
    """Instantiate the given module classes, register them, and bind the registry to ``app.modules``.

    :param app: Application owning the registry.
    :param module_classes: Module classes to instantiate with ``app`` and register.
    :returns: Populated registry bound to ``app.modules``.
    """
    registry = ModuleRegistry()
    app.modules = registry
    for cls in module_classes:
        module = cls(app)
        registry.register(module)
    return registry

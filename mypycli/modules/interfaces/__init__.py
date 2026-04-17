from .commandable import Commandable
from .daemonic import Daemonic
from .installable import Installable
from .startable import Startable
from .statusable import Statusable
from .updatable import Updatable

# Tuple of all module interface classes, used for introspection
ALL_INTERFACES = (Startable, Statusable, Daemonic, Installable, Updatable, Commandable)

__all__ = [
    "ALL_INTERFACES",
    "Commandable",
    "Daemonic",
    "Installable",
    "Startable",
    "Statusable",
    "Updatable",
]

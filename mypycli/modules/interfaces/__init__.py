from .commandable import Commandable
from .daemonic import Daemonic
from .installable import Installable
from .startable import Startable
from .statusable import Statusable
from .updatable import Updatable

MODULES_INTERFACES = (
    Startable,
    Statusable,
    Daemonic,
    Installable,
    Updatable,
    Commandable,
)

__all__ = [
    "MODULES_INTERFACES",
    "Commandable",
    "Daemonic",
    "Installable",
    "Startable",
    "Statusable",
    "Updatable",
]

from __future__ import annotations

from enum import Enum


class ByteUnit(int, Enum):
    """Binary byte units with 1024-based multipliers."""

    B = 1
    KB = 1024
    MB = 1024**2
    GB = 1024**3
    TB = 1024**4

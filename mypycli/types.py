from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from pydantic import BaseModel, field_validator
from rich.text import Text

if TYPE_CHECKING:
    from argparse import Namespace
    from collections.abc import Callable

    from mypycli.application import Application

DEFAULT_LANGUAGE_CODE: str = "en"
SUPPORTED_LANGUAGE_CODES: tuple[str, ...] = ("ru", "en", "zh")

PANEL_SEPARATOR: tuple[Text, Text] = (Text(""), Text(""))


class Mode(str, Enum):
    PROMPT = "prompt"
    DAEMON = "daemon"


class Color(str, Enum):
    red = "red"
    blue = "blue"
    cyan = "cyan"
    gray = "bright_black"
    green = "green"
    yellow = "yellow"
    magenta = "magenta"

    def __call__(self, text: str) -> Text:
        return Text(text, style=self.value)


@dataclass
class Command:
    name: str
    handler: Callable[[Application, list[str]], bool] | None = None
    description: str = ""
    usage: str = ""


@dataclass
class CommandGroup:
    name: str
    description: str = ""
    commands: list[Command | CommandGroup] = field(default_factory=list)


@dataclass
class CliCommand:
    name: str
    description: str
    handler: Callable[[Application, Namespace], None]
    needs_root: bool = False


@dataclass
class ServiceStatus:
    active: bool
    pid: int | None
    uptime: int | None


class ByteUnit(str, Enum):
    B = "B"
    KiB = "KiB"
    KB = "KB"
    MiB = "MiB"
    MB = "MB"
    GiB = "GiB"
    GB = "GB"
    TiB = "TiB"
    TB = "TB"


class BitUnit(str, Enum):
    bit = "bit"
    kbit = "kbit"
    Mbit = "Mbit"
    Gbit = "Gbit"
    Tbit = "Tbit"


class OSInfo(BaseModel):
    name: str
    release: str
    version: str
    machine: str


class HardwareInfo(BaseModel):
    product_name: str | None = None
    is_virtualized: bool | None = None


class CpuInfo(BaseModel):
    name: str | None = None
    count_logical: int
    count_physical: int
    load_1m: float
    load_5m: float
    load_15m: float

    @field_validator("load_1m", "load_5m", "load_15m")
    @classmethod
    def _round_load(cls, v: float) -> float:
        return round(v, 2)


class MemoryInfo(BaseModel):
    total: int
    used: int
    free: int
    usage_percent: float


class DiskSpaceInfo(BaseModel):
    path: str
    total: int
    used: int
    free: int
    usage_percent: float
    device_name: str | None = None


class DiskIOInfo(BaseModel):
    read_bytes: int
    write_bytes: int
    read_count: int
    write_count: int
    busy_time: int


class NetworkIOInfo(BaseModel):
    bytes_sent: int
    bytes_recv: int
    packets_sent: int
    packets_recv: int

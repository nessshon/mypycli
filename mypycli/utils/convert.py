from __future__ import annotations

import re
import time as _time
from typing import Literal

from mypycli.types.units import ByteUnit

_BYTE_UNITS: dict[str, int] = {
    "": 1,
    "B": 1,
    "K": 1024,
    "KB": 1024,
    "M": 1024**2,
    "MB": 1024**2,
    "G": 1024**3,
    "GB": 1024**3,
    "T": 1024**4,
    "TB": 1024**4,
}

_DURATION_FORMS: dict[str, dict[str, object]] = {
    "en": {
        "unknown": "unknown",
        "just_now": "just now",
        "ago": "{duration} ago",
        "second": ("{n} second", "{n} seconds"),
        "minute": ("{n} minute", "{n} minutes"),
        "hour": ("{n} hour", "{n} hours"),
        "day": ("{n} day", "{n} days"),
    },
    "ru": {
        "unknown": "неизвестно",
        "just_now": "только что",
        "ago": "{duration} назад",
        "second": ("{n} секунду", "{n} секунды", "{n} секунд"),
        "minute": ("{n} минуту", "{n} минуты", "{n} минут"),
        "hour": ("{n} час", "{n} часа", "{n} часов"),
        "day": ("{n} день", "{n} дня", "{n} дней"),
    },
    "zh": {
        "unknown": "未知",
        "just_now": "刚刚",
        "ago": "{duration}前",
        "second": ("{n} 秒",),
        "minute": ("{n} 分钟",),
        "hour": ("{n} 小时",),
        "day": ("{n} 天",),
    },
}

_BYTES_RE = re.compile(r"^\s*([+-]?\d+(?:\.\d+)?)\s*([A-Z]*)\s*$", re.IGNORECASE)

_DURATION_UNITS: dict[str, int] = {"s": 1, "m": 60, "h": 3600, "d": 86400}

_DURATION_PART_RE = re.compile(r"(\d+(?:\.\d+)?)\s*([smhd])", re.IGNORECASE)


def bytes_to(n: int | float, unit: ByteUnit) -> float:
    """Convert a byte count into the given binary unit (KB/MB/GB/TB)."""
    return n / unit


def format_bytes(
    n: int | float,
    *,
    unit: ByteUnit | None = None,
    precision: int = 2,
) -> str:
    """Format a byte count as a human-readable string with unit suffix.

    :param n: Byte count to format.
    :param unit: Target unit; when ``None`` picks the largest unit that keeps the value >= 1.
    :param precision: Number of decimal places to render.
    """
    if unit is None:
        for candidate in (ByteUnit.TB, ByteUnit.GB, ByteUnit.MB, ByteUnit.KB):
            if abs(n) >= candidate:
                unit = candidate
                break
        else:
            unit = ByteUnit.B
    return f"{n / unit:.{precision}f} {unit.name}"


def format_bitrate(bits_per_sec: int | float, *, precision: int = 2) -> str:
    """Format a data rate in bits/second as a human-readable string.

    Uses decimal (1000-based) prefixes — Kbit/s, Mbit/s, Gbit/s — the
    standard convention for network throughput.

    :param bits_per_sec: Rate in bits per second.
    :param precision: Number of decimal places to render.
    """
    for factor, name in (
        (1000**3, "Gbit/s"),
        (1000**2, "Mbit/s"),
        (1000, "Kbit/s"),
    ):
        if abs(bits_per_sec) >= factor:
            return f"{bits_per_sec / factor:.{precision}f} {name}"
    return f"{bits_per_sec:.{precision}f} bit/s"


def format_duration(seconds: int | float | None, *, lang: Literal["en", "ru", "zh"] = "en") -> str:
    """Format a duration picking the largest whole unit (seconds/minutes/hours/days).

    :param seconds: Duration to format; ``None`` yields the localized ``unknown`` marker.
    :param lang: Output language.
    """
    def _pick_form(n: int, forms_: tuple[str, ...]) -> str:
        if lang == "ru":
            if n % 10 == 1 and n % 100 != 11:
                return forms_[0]
            if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
                return forms_[1]
            return forms_[2]
        if lang == "zh":
            return forms_[0]
        return forms_[0] if n == 1 else forms_[1]

    forms = _DURATION_FORMS[lang]
    if seconds is None:
        return str(forms["unknown"])
    s = int(seconds)
    if s < 60:
        unit = "second"
        value = s
    elif s < 3600:
        unit = "minute"
        value = s // 60
    elif s < 86400:
        unit = "hour"
        value = s // 3600
    else:
        unit = "day"
        value = s // 86400
    template = _pick_form(value, forms[unit])  # type: ignore[arg-type]
    return template.format(n=value)


def format_time_ago(timestamp: int | float | None, *, lang: Literal["en", "ru", "zh"] = "en") -> str:
    """Format a Unix timestamp as a relative past duration.

    :param timestamp: Unix epoch seconds; ``None`` yields the localized ``unknown`` marker.
    :param lang: Output language.
    """
    forms = _DURATION_FORMS[lang]
    if timestamp is None:
        return str(forms["unknown"])
    diff = int(_time.time() - timestamp)
    if diff < 60:
        return str(forms["just_now"])
    duration = format_duration(diff, lang=lang)
    return str(forms["ago"]).format(duration=duration)


def parse_bytes(value: str) -> int:
    """Parse a human-readable size string into a byte count using binary 1024-based units.

    Accepts an optional unit suffix (``B``/``K``/``KB``/``M``/``MB``/``G``/``GB``/``T``/``TB``),
    case-insensitive; a bare number is treated as bytes.

    :raises ValueError: If the format is invalid or the unit is unknown.
    """
    match = _BYTES_RE.match(value)
    if not match:
        raise ValueError(f"Invalid byte size: {value!r}")
    number, unit = match.groups()
    unit_upper = unit.upper()
    if unit_upper not in _BYTE_UNITS:
        raise ValueError(f"Unknown byte unit: {unit!r}")
    return int(float(number) * _BYTE_UNITS[unit_upper])


def parse_duration(value: str) -> int:
    """Parse a duration string into whole seconds, summing ``s``/``m``/``h``/``d`` parts.

    A bare number is interpreted as seconds; otherwise components like ``"1h30m"`` are added together.

    :raises ValueError: If the input has no recognizable parts or contains trailing garbage.
    """
    stripped = value.strip()
    try:
        return int(float(stripped))
    except ValueError:
        pass

    matches = _DURATION_PART_RE.findall(stripped)
    if not matches:
        raise ValueError(f"Invalid duration: {value!r}")

    leftover = _DURATION_PART_RE.sub("", stripped).strip()
    if leftover:
        raise ValueError(f"Invalid duration: {value!r} (unparsed: {leftover!r})")

    total = 0.0
    for number, unit in matches:
        total += float(number) * _DURATION_UNITS[unit.lower()]
    return int(total)

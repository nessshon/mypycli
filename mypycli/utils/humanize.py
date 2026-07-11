import time
from typing import TypedDict

from mypycli.types import BitUnit, ByteUnit
from mypycli.utils.convert import (
    _BIT_DIVISORS,
    _BYTE_DIVISORS,
)


class DurationForms(TypedDict):
    unknown: str
    just_now: str
    ago: str
    second: tuple[str, ...]
    minute: tuple[str, ...]
    hour: tuple[str, ...]
    day: tuple[str, ...]


_DURATION_FORMS: dict[str, DurationForms] = {
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


def _plural(n: int, forms: tuple[str, ...], lang: str) -> str:
    if lang == "ru":
        mod10 = n % 10
        mod100 = n % 100
        if mod10 == 1 and mod100 != 11:
            return forms[0]
        if 2 <= mod10 <= 4 and not 12 <= mod100 <= 14:
            return forms[1]
        return forms[2]
    if lang == "zh":
        return forms[0]
    return forms[0] if n == 1 else forms[1]


def humanize_duration(seconds: int | float | None, *, lang: str = "en") -> str:
    forms = _DURATION_FORMS[lang]
    if seconds is None:
        return forms["unknown"]
    s = int(seconds)
    if s < 60:
        n = s
        word_forms = forms["second"]
    elif s < 3600:
        n = s // 60
        word_forms = forms["minute"]
    elif s < 86400:
        n = s // 3600
        word_forms = forms["hour"]
    else:
        n = s // 86400
        word_forms = forms["day"]
    template = _plural(n, word_forms, lang)
    return template.format(n=n)


def humanize_time_ago(timestamp: int | float | None, *, lang: str = "en") -> str:
    forms = _DURATION_FORMS[lang]
    if timestamp is None:
        return forms["unknown"]
    diff = int(time.time() - timestamp)
    if diff < 60:
        return forms["just_now"]
    duration = humanize_duration(diff, lang=lang)
    return forms["ago"].format(duration=duration)


def humanize_bytes(value: int, *, decimals: int = 2) -> str:
    for unit in (ByteUnit.TiB, ByteUnit.GiB, ByteUnit.MiB, ByteUnit.KiB):
        divisor = _BYTE_DIVISORS[unit]
        if abs(value) >= divisor:
            return f"{round(value / divisor, decimals)} {unit.value}"
    return f"{value} {ByteUnit.B.value}"


def humanize_bits(value: int, *, decimals: int = 2) -> str:
    bits = value * 8
    for unit in (BitUnit.Tbit, BitUnit.Gbit, BitUnit.Mbit, BitUnit.kbit):
        divisor = _BIT_DIVISORS[unit]
        if abs(bits) >= divisor:
            return f"{round(bits / divisor, decimals)} {unit.value}"
    return f"{bits} {BitUnit.bit.value}"


def humanize_byterate(bytes_per_sec: float, *, decimals: int = 2) -> str:
    return f"{humanize_bytes(int(bytes_per_sec), decimals=decimals)}/s"


def humanize_bitrate(bytes_per_sec: float, *, decimals: int = 2) -> str:
    return f"{humanize_bits(int(bytes_per_sec), decimals=decimals)}/s"

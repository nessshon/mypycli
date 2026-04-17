from __future__ import annotations

import time as _time

import pytest

from mypycli.types import ByteUnit
from mypycli.utils.convert import (
    bytes_to,
    format_bitrate,
    format_bytes,
    format_duration,
    format_time_ago,
    parse_bytes,
    parse_duration,
)


class TestBytesTo:
    @pytest.mark.parametrize(
        ("value", "unit", "expected"),
        [
            (1024, ByteUnit.B, 1024),
            (1024, ByteUnit.KB, 1.0),
            (1024**2, ByteUnit.MB, 1.0),
            (int(1.5 * 1024**3), ByteUnit.GB, 1.5),
        ],
    )
    def test_division(self, value: int, unit: ByteUnit, expected: float) -> None:
        assert bytes_to(value, unit) == expected


class TestFormatBytes:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (0, "0.00 B"),
            (512, "512.00 B"),
            (1536, "1.50 KB"),
            (2 * 1024**2, "2.00 MB"),
            (3 * 1024**3, "3.00 GB"),
        ],
    )
    def test_auto_unit(self, value: int, expected: str) -> None:
        assert format_bytes(value) == expected

    def test_explicit_unit(self) -> None:
        assert format_bytes(1024**3, unit=ByteUnit.MB) == "1024.00 MB"

    def test_precision(self) -> None:
        assert format_bytes(1024**3, precision=0) == "1 GB"


class TestFormatBitrate:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (500, "500.00 bit/s"),
            (1500, "1.50 Kbit/s"),
            (125_000_000, "125.00 Mbit/s"),
            (2_500_000_000, "2.50 Gbit/s"),
        ],
    )
    def test_unit_boundaries(self, value: int, expected: str) -> None:
        assert format_bitrate(value) == expected

    def test_negative_uses_abs_for_threshold(self) -> None:
        assert format_bitrate(-125_000_000) == "-125.00 Mbit/s"

    def test_precision_zero(self) -> None:
        assert format_bitrate(125_000_000, precision=0) == "125 Mbit/s"


class TestFormatDuration:
    @pytest.mark.parametrize(
        ("seconds", "expected"),
        [
            (None, "unknown"),
            (0, "0 seconds"),
            (1, "1 second"),
            (45, "45 seconds"),
            (60, "1 minute"),
            (120, "2 minutes"),
            (3600, "1 hour"),
            (86400, "1 day"),
            (172800, "2 days"),
        ],
    )
    def test_en_default(self, seconds: int | None, expected: str) -> None:
        assert format_duration(seconds) == expected

    @pytest.mark.parametrize(
        ("seconds", "expected"),
        [
            (None, "неизвестно"),
            (1, "1 секунду"),
            (2, "2 секунды"),
            (5, "5 секунд"),
            (11, "11 секунд"),
            (21, "21 секунду"),
            (22, "22 секунды"),
            (60, "1 минуту"),
            (180, "3 минуты"),
            (3600, "1 час"),
            (7200, "2 часа"),
            (18000, "5 часов"),
            (86400, "1 день"),
            (172800, "2 дня"),
            (432000, "5 дней"),
        ],
    )
    def test_ru_plural(self, seconds: int | None, expected: str) -> None:
        assert format_duration(seconds, lang="ru") == expected

    @pytest.mark.parametrize(
        ("seconds", "expected"),
        [
            (None, "未知"),
            (1, "1 秒"),
            (5, "5 秒"),
            (60, "1 分钟"),
            (300, "5 分钟"),
            (3600, "1 小时"),
            (86400, "1 天"),
        ],
    )
    def test_zh_single_form(self, seconds: int | None, expected: str) -> None:
        assert format_duration(seconds, lang="zh") == expected

class TestFormatTimeAgo:
    def test_none_en(self) -> None:
        assert format_time_ago(None) == "unknown"

    def test_none_ru(self) -> None:
        assert format_time_ago(None, lang="ru") == "неизвестно"

    def test_none_zh(self) -> None:
        assert format_time_ago(None, lang="zh") == "未知"

    def test_just_now_en(self) -> None:
        assert format_time_ago(_time.time()) == "just now"

    def test_just_now_ru(self) -> None:
        assert format_time_ago(_time.time(), lang="ru") == "только что"

    def test_just_now_zh(self) -> None:
        assert format_time_ago(_time.time(), lang="zh") == "刚刚"

    def test_past_en(self) -> None:
        assert format_time_ago(_time.time() - 120) == "2 minutes ago"

    def test_past_ru_plural_form(self) -> None:
        assert format_time_ago(_time.time() - 120, lang="ru") == "2 минуты назад"
        assert format_time_ago(_time.time() - 60, lang="ru") == "1 минуту назад"
        assert format_time_ago(_time.time() - 300, lang="ru") == "5 минут назад"

    def test_past_zh_has_no_space_before_suffix(self) -> None:
        assert format_time_ago(_time.time() - 300, lang="zh") == "5 分钟前"


class TestParseBytes:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("1024", 1024),
            ("512B", 512),
            ("1KB", 1024),
            ("1 KB", 1024),
            ("10G", 10 * 1024**3),
            ("100mb", 100 * 1024**2),
            ("1.5GB", int(1.5 * 1024**3)),
        ],
    )
    def test_parses(self, text: str, expected: int) -> None:
        assert parse_bytes(text) == expected

    @pytest.mark.parametrize("bad", ["invalid", "10XB", ""])
    def test_rejects(self, bad: str) -> None:
        with pytest.raises(ValueError):
            parse_bytes(bad)

    def test_roundtrip_with_format_bytes(self) -> None:
        for n in (0, 1024, 1536, 1024**3, int(2.5 * 1024**2)):
            assert parse_bytes(format_bytes(n)) == n


class TestParseDuration:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("30", 30),
            ("30s", 30),
            ("5m", 300),
            ("2h", 7200),
            ("7d", 7 * 86400),
            ("1h30m", 5400),
            ("1h 30m 15s", 5415),
            ("1d2h3m4s", 86400 + 7200 + 180 + 4),
            ("1H30M", 5400),
        ],
    )
    def test_parses(self, text: str, expected: int) -> None:
        assert parse_duration(text) == expected

    @pytest.mark.parametrize("bad", ["invalid", "5x", "1h junk"])
    def test_rejects(self, bad: str) -> None:
        with pytest.raises(ValueError):
            parse_duration(bad)

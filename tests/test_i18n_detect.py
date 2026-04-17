import pytest

from mypycli.i18n.detect import parse_lang_env


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("en_US.UTF-8", "en"),
        ("ru_RU", "ru"),
        ("zh", "zh"),
        ("en", "en"),
        ("C", ""),
        ("C.UTF-8", ""),
        ("POSIX", ""),
        ("", ""),
        ("EN_US.UTF-8", "en"),
        ("RU", "ru"),
        ("xyz", ""),
        ("e", ""),
    ],
)
def test_parse_lang_env(raw: str, expected: str) -> None:
    assert parse_lang_env(raw) == expected

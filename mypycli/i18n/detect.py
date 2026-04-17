from __future__ import annotations

import re

_VALID_LANG_RE = re.compile(r"^[a-z]{2}$")


def parse_lang_env(raw: str) -> str:
    """Parse env LANG-style string to a 2-letter lowercase code, or empty string."""
    if not raw:
        return ""
    head = raw.split(".", 1)[0].split("_", 1)[0].lower()
    return head if _VALID_LANG_RE.match(head) else ""

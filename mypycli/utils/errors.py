from __future__ import annotations

from pydantic import ValidationError


def format_validation_error(exc: BaseException) -> str:
    """Render a pydantic ValidationError as semicolon-separated ``field.path: message`` entries.

    :param exc: Exception to format; non-pydantic exceptions fall back to ``str(exc)``.
    """
    if not isinstance(exc, ValidationError):
        return str(exc)
    parts: list[str] = []
    for err in exc.errors():
        loc = ".".join(str(x) for x in err["loc"]) or "?"
        parts.append(f"{loc}: {err['msg']}")
    return "; ".join(parts) if parts else str(exc)

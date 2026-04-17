from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from mypycli.types.console import ColorText


@dataclass(frozen=True)
class Input:
    """Free-form text input prompt.

    :param prompt: Prompt label shown to the user.
    :param default: Value returned when the user submits empty input.
    :param validate: Optional callable returning ``None`` on success or an error string
        to display; on a TTY the prompt is retried with the entered buffer preserved,
        on non-TTY a ``ValueError`` is raised.
    """

    prompt: str | ColorText
    default: str | ColorText | None = None
    validate: Callable[[str], str | None] | None = None


@dataclass(frozen=True)
class Secret:
    """Masked text input prompt for sensitive values.

    :param prompt: Prompt label shown to the user.
    :param validate: Optional callable returning ``None`` on success or an error string
        to display; on a TTY the prompt is retried, on non-TTY a ``ValueError`` is raised.
    """

    prompt: str | ColorText
    validate: Callable[[str], str | None] | None = None


@dataclass(frozen=True)
class Confirm:
    """Yes/no confirmation prompt.

    :param prompt: Question shown to the user.
    :param default: Value returned when the user submits empty input.
    """

    prompt: str | ColorText
    default: bool = False


@dataclass(frozen=True)
class Select:
    """Single-choice selection prompt.

    :param prompt: Label displayed above the list of choices.
    :param choices: Available options.
    :param default: Option pre-selected when the prompt opens.
    """

    prompt: str | ColorText
    choices: list[str | ColorText] = field(default_factory=list)
    default: str | None = None


@dataclass(frozen=True)
class Multiselect:
    """Multi-choice selection prompt.

    :param prompt: Label displayed above the list of choices.
    :param choices: Available options.
    """

    prompt: str | ColorText
    choices: list[str | ColorText] = field(default_factory=list)

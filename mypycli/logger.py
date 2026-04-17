"""Two-channel model: the logger writes to a rotating log file only.

The terminal UX channel belongs to ``Console`` (``app.console.print`` and
friends). This module never writes to stdout — ``add_file_handler`` is the
only attachment the framework uses, so diagnostics stay out of the user's
interactive view and remain intact for operators tailing the file.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

DEFAULT_DATEFMT = "%Y-%m-%d %H:%M:%S"


class PlainFormatter(logging.Formatter):
    """Logging formatter that renders records as plain text for file output."""

    def format(self, record: logging.LogRecord) -> str:
        """Format ``record`` as ``[LEVEL] timestamp <thread> name: message`` without ANSI codes.

        Appends traceback (``record.exc_info``) and stack info when present.

        :param record: Log record to format.
        """
        level = f"[{record.levelname:<8}]"
        thread = f"<{record.threadName}>"
        message = record.getMessage()
        timestamp = self.formatTime(record, self.datefmt)
        line = f"{level} {timestamp} {thread} {record.name}: {message}"
        return _append_exc_info(line, record, self)


def _append_exc_info(line: str, record: logging.LogRecord, fmt: logging.Formatter) -> str:
    """Return ``line`` extended with the record's traceback and stack info when present."""
    if record.exc_info:
        if not record.exc_text:
            record.exc_text = fmt.formatException(record.exc_info)
        line = f"{line}\n{record.exc_text}"
    if record.stack_info:
        line = f"{line}\n{fmt.formatStack(record.stack_info)}"
    return line


def setup_logger(
    name: str,
    *,
    level: int = logging.INFO,
) -> logging.Logger:
    """Configure and return a named logger with a NullHandler.

    The file handler is attached later via ``add_file_handler`` (invoked from
    ``Application.enable_file_logging``); before that the logger absorbs records
    silently.

    :param name: Logger name passed to ``logging.getLogger``.
    :param level: Minimum level for the logger.
    """
    log = logging.getLogger(name)
    log.setLevel(level)
    log.handlers.clear()
    log.addHandler(logging.NullHandler())
    return log


def add_file_handler(
    logger: logging.Logger,
    log_file: str | Path,
    *,
    max_bytes: int = 5 * 1_048_576,
    backup_count: int = 5,
    datefmt: str = DEFAULT_DATEFMT,
) -> None:
    """Attach a ``RotatingFileHandler`` formatted via ``PlainFormatter``.

    :param logger: Target logger.
    :param log_file: Path to the log file.
    :param max_bytes: Rotation threshold in bytes.
    :param backup_count: Number of rotated files to retain.
    :param datefmt: Timestamp format for the plain formatter.
    """
    path = Path(log_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    handler.setFormatter(PlainFormatter(datefmt=datefmt))
    logger.addHandler(handler)

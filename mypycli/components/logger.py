import io
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import TYPE_CHECKING, Any

from rich.console import Console as RichConsole
from rich.logging import RichHandler
from rich.traceback import Traceback

if TYPE_CHECKING:
    _LoggerAdapter = logging.LoggerAdapter[logging.Logger]
else:
    _LoggerAdapter = logging.LoggerAdapter


class _PrefixFilter(logging.Filter):
    def __init__(self) -> None:
        super().__init__()
        self.prefix = ""

    def filter(self, record: logging.LogRecord) -> bool:
        record.prefix = self.prefix
        return True


class _RichFormatter(logging.Formatter):
    def formatException(self, ei: Any) -> str:
        buf = io.StringIO()
        console = RichConsole(
            file=buf,
            force_terminal=False,
            no_color=True,
            width=120,
        )
        tb = Traceback.from_exception(
            *ei,
            show_locals=False,
            word_wrap=True,
        )
        console.print(tb)
        return buf.getvalue().rstrip()


class Logger(_LoggerAdapter):
    FILE_FORMAT: str = "%(asctime)s %(levelname)-8s %(prefix)s%(name)s: %(message)s"
    RICH_FORMAT: str = "%(prefix)s%(name)s: %(message)s"
    DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"
    MAX_FILE_SIZE: int = 10 * 1024 * 1024
    BACKUPS_COUNT: int = 10

    def __init__(
        self,
        name: str,
        debug: bool,
        logs_dir: str | Path,
        *,
        file_format: str = FILE_FORMAT,
        rich_format: str = RICH_FORMAT,
        date_format: str = DATE_FORMAT,
        max_file_size: int = MAX_FILE_SIZE,
        backups_count: int = BACKUPS_COUNT,
    ) -> None:
        self._file_format = file_format
        self._rich_format = rich_format
        self._date_format = date_format
        self._max_file_size = max_file_size
        self._backups_count = backups_count

        self._path = Path(logs_dir) / f"{name}.log"
        self._filter = _PrefixFilter()

        level = logging.DEBUG if debug else logging.INFO
        logger = logging.getLogger(name)
        self._configure_logger(logger, level)
        super().__init__(logger)

    def set_prefix(self, prefix: str) -> None:
        self._filter.prefix = f"[{prefix}] " if prefix else ""

    def _configure_logger(self, logger: logging.Logger, level: int) -> None:
        logger.setLevel(level)
        logger.propagate = False
        for handler in logger.handlers:
            handler.close()
        logger.handlers.clear()
        logger.addHandler(self._create_file_handler())
        logger.addHandler(self._create_rich_handler())

    def _create_file_handler(self) -> RotatingFileHandler:
        handler = RotatingFileHandler(
            self._path,
            encoding="utf-8",
            maxBytes=self._max_file_size,
            backupCount=self._backups_count,
        )
        handler.setFormatter(_RichFormatter(self._file_format, self._date_format))
        handler.addFilter(self._filter)
        return handler

    def _create_rich_handler(self) -> RichHandler:
        handler = RichHandler(
            console=RichConsole(stderr=True),
            log_time_format=self._date_format,
            tracebacks_show_locals=False,
            omit_repeated_times=False,
            rich_tracebacks=True,
            show_path=False,
        )
        handler.setFormatter(logging.Formatter(self._rich_format))
        handler.addFilter(self._filter)
        return handler

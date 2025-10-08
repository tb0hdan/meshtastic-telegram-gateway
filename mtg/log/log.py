# -*- coding: utf-8 -*-
"""Logger module with rotation helpers."""

import json
import logging
import os
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Optional, Union

with open('VERSION', 'r', encoding='utf-8') as fh:
    VERSION = fh.read().rstrip('\n')
LOGFORMAT = '%(asctime)s - %(name)s/v{} - %(levelname)s file:%(filename)s %(funcName)s line:%(lineno)s %(message)s'
LOGFORMAT = LOGFORMAT.format(VERSION)


class JsonFormatter(logging.Formatter):
    """Simple JSON log formatter"""

    def format(self, record: logging.LogRecord) -> str:  # type: ignore[override]
        base = {
            "time": self.formatTime(record, self.datefmt),
            "name": f"{record.name}/v{VERSION}",
            "level": record.levelname,
            "message": record.getMessage(),
        }
        if record.exc_info:
            base["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(base)


class SizedTimedRotatingFileHandler(TimedRotatingFileHandler):
    """Rotate log files by time and size."""

    def __init__(
        self,
        filename: Union[str, os.PathLike],
        *,
        max_bytes: int,
        backup_count: int,
        when: str = "midnight",
        interval: int = 1,
        encoding: Optional[str] = None,
        delay: bool = False,
        utc: bool = False,
        at_time=None,
    ) -> None:
        super().__init__(
            filename,
            when=when,
            interval=interval,
            backupCount=backup_count,
            encoding=encoding,
            delay=delay,
            utc=utc,
            atTime=at_time,
        )
        self.maxBytes = max_bytes

    # pylint: disable=arguments-differ
    def shouldRollover(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        if self.maxBytes > 0:
            if self.stream is None:
                self.stream = self._open()
            if self.stream is not None:
                self.stream.seek(0, os.SEEK_END)
                current_size = self.stream.tell()
                if current_size >= self.maxBytes:
                    return True
                message = f"{self.format(record)}\n"
                if current_size + len(message) >= self.maxBytes:
                    return True
        return super().shouldRollover(record)


def setup_logger(
    name: str = __name__,
    level: int = logging.INFO,
    *,
    json_logs: bool = False,
    log_dir: Optional[Union[str, os.PathLike]] = None,
    max_bytes: int = 1_000_000_000,
    backup_count: int = 15,
) -> logging.Logger:
    """
    Set up logger and return usable instance

    :param name:
    :param level:

    :return:
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False
    if logger.handlers:
        logger.handlers.clear()

    # create console handler and set level to debug
    handler = logging.StreamHandler()
    handler.setLevel(level)

    # create formatter
    if json_logs:
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(LOGFORMAT)

    # add formatter to ch
    handler.setFormatter(formatter)

    # add ch to logger
    logger.addHandler(handler)

    resolved_log_dir: Path
    if log_dir is None:
        env_dir = os.getenv("MTG_LOG_DIR")
        resolved_log_dir = Path(env_dir) if env_dir else Path.cwd() / "logs"
    else:
        resolved_log_dir = Path(log_dir)
    resolved_log_dir.mkdir(parents=True, exist_ok=True)
    log_path = resolved_log_dir / f"{name}.log"

    rotating_handler = SizedTimedRotatingFileHandler(
        log_path,
        max_bytes=max_bytes,
        backup_count=backup_count,
    )
    rotating_handler.setLevel(level)
    rotating_handler.setFormatter(formatter)
    logger.addHandler(rotating_handler)

    return logger


def conditional_log(message, logger, condition) -> None:
    """
    conditional_log - log message when condition is true

    :param message:
    :param logger:
    :param condition:
    :return:
    """
    return logger.debug(message) if condition else None

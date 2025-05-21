# -*- coding: utf-8 -*-
""" Logger module """

import logging
import json

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


def setup_logger(name: str = __name__, level: int = logging.INFO, *, json_logs: bool = False) -> logging.Logger:
    """
    Set up logger and return usable instance

    :param name:
    :param level:

    :return:
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False

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

# -*- coding: utf-8 -*-
""" Logger module """

import logging

with open('VERSION', 'r', encoding='utf-8') as fh:
    VERSION = fh.read().rstrip('\n')
LOGFORMAT = '%(asctime)s - %(name)s/v{} - %(levelname)s file:%(filename)s %(funcName)s line:%(lineno)s %(message)s'
LOGFORMAT = LOGFORMAT.format(VERSION)


def setup_logger(name=__name__, level=logging.INFO) -> logging.Logger:
    """
    Set up logger and return usable instance

    :param name:
    :param level:

    :return:
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # create console handler and set level to debug
    handler = logging.StreamHandler()
    handler.setLevel(level)

    # create formatter
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

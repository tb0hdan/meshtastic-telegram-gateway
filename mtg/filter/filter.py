# -*- coding: utf-8 -*-
""" Filter module """

import logging

from mtg.database import MeshtasticDB
from mtg.config import Config


class Filter:
    """
    Filter parent class
    """
    connection_type = ""

    def __init__(self, database: MeshtasticDB, config: Config, logger: logging.Logger):
        self.database = database
        self.config = config
        self.logger = logger

    def banned(self, identifier) -> bool:
        """
        banned - returns True if identifier is banned
        """
        status, record = self.database.get_filter(self.connection_type, identifier)
        if not status:
            return False
        self.logger.error(f"{identifier} is ban:{record.active} for {self.connection_type}")
        return record.active


class TelegramFilter(Filter):
    """
    Telegram users filter
    """

    def __init__(self, database: MeshtasticDB, config: Config, logger: logging.Logger):
        super().__init__(database, config, logger)
        self.database = database
        self.config = config
        self.connection_type = "Telegram"
        self.logger = logger


class MeshtasticFilter(Filter):
    """
    Meshtastic users filter
    """

    def __init__(self, database: MeshtasticDB, config: Config, logger: logging.Logger):
        super().__init__(database, config, logger)
        self.database = database
        self.config = config
        self.connection_type = "Meshtastic"
        self.logger = logger


class CallSignFilter(Filter):
    """
    APRS callsign filter
    """

    def __init__(self, database: MeshtasticDB, config: Config, logger: logging.Logger):
        super().__init__(database, config, logger)
        self.database = database
        self.config = config
        self.connection_type = "Callsign"
        self.logger = logger

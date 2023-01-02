import logging

from mtg.database import MeshtasticDB
from mtg.config import Config
from mtg.connection.meshtastic import MeshtasticConnection

class Filter:
    """
    Filter parent class
    """
    connection_type = ""

    def __init__(self, database: MeshtasticDB, config: Config, connection: MeshtasticConnection,
                 logger: logging.Logger):
        self.database = database
        self.connection = connection
        self.config = config
        self.logger = logger


class TelegramFilter(Filter):
    """
    Telegram users filter
    """
    def __init__(self, database: MeshtasticDB, config: Config, connection: MeshtasticConnection,
                 logger: logging.Logger):
        super().__init__(database, config, connection, logger)
        self.database = database
        self.config = config
        self.connection = connection
        self.connection_type = "Telegram"
        self.logger = logger


class MeshtasticFilter(Filter):
    """
    Meshtastic users filter
    """
    def __init__(self, database: MeshtasticDB, config: Config, connection: MeshtasticConnection,
                 logger: logging.Logger):
        super().__init__(database, config, connection, logger)
        self.database = database
        self.config = config
        self.connection = connection
        self.connection_type = "Meshtastic"
        self.logger = logger


class CallSignFilter(Filter):
    """
    APRS callsign filter
    """
    def __init__(self, database: MeshtasticDB, config: Config, connection: MeshtasticConnection,
                 logger: logging.Logger):
        super().__init__(database, config, connection, logger)
        self.database = database
        self.config = config
        self.connection = connection
        self.connection_type = "Callsign"
        self.logger = logger

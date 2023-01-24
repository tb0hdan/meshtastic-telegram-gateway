#-*- coding: utf-8 -*-
""" Rich Meshtastic connection. Original one fused with DB features """

import logging
import time

from mtg.connection.meshtastic import MeshtasticConnection


class RichConnection(MeshtasticConnection):
    """
    RichConnection - enriched Meshtastic connection
    """
    def __init__(self, dev_path: str, logger: logging.Logger, config, startup_ts = time.time()):
        super().__init__(dev_path, logger, config, startup_ts)

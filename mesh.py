#!/usr/bin/env python3
"""Meshtastic Telegram Gateway"""

#
import logging
import os
import sys
import time
#
#
from mtg.bot.meshtastic import MeshtasticBot
from mtg.bot.telegram import TelegramBot
from mtg.config import Config
from mtg.connection.aprs import APRSStreamer
from mtg.connection.meshtastic import MeshtasticConnection
from mtg.connection.telegram import TelegramConnection
from mtg.database import sql_debug, MeshtasticDB
from mtg.filter import CallSignFilter, MeshtasticFilter, TelegramFilter
from mtg.log import setup_logger, LOGFORMAT
from mtg.webapp import WebServer
#

# pylint:disable=too-many-locals
def main():
    """
    Main function :)

    :return:
    """
    config = Config()
    config.read()
    level = logging.INFO
    if config.enforce_type(bool, config.DEFAULT.Debug):
        level = logging.DEBUG
        sql_debug()

    # our logger
    logger = setup_logger('mesh', level)
    # meshtastic logger
    logging.basicConfig(level=level,
                        format=LOGFORMAT)
    basedir = os.path.abspath(os.path.dirname(__file__))
    #
    telegram_connection = TelegramConnection(config.Telegram.Token, logger)
    meshtastic_connection = MeshtasticConnection(config.Meshtastic.Device, logger)
    meshtastic_connection.connect()
    database = MeshtasticDB(os.path.join(basedir, config.Meshtastic.DatabaseFile),
                            meshtastic_connection, logger)
    #
    aprs_streamer = APRSStreamer(config)
    call_sign_filter = CallSignFilter(database, config, meshtastic_connection, logger)
    aprs_streamer.set_filter(call_sign_filter)
    aprs_streamer.set_logger(logger)
    #
    telegram_bot = TelegramBot(config, meshtastic_connection, telegram_connection)
    telegram_filter = TelegramFilter(database, config, meshtastic_connection, logger)
    telegram_bot.set_filter(telegram_filter)
    telegram_bot.set_logger(logger)
    #
    meshtastic_bot = MeshtasticBot(database, config, meshtastic_connection, telegram_connection)
    meshtastic_filter = MeshtasticFilter(database, config, meshtastic_connection, logger)
    meshtastic_bot.set_filter(meshtastic_filter)
    meshtastic_bot.set_logger(logger)
    meshtastic_bot.subscribe()
    #
    template_folder = os.path.join(basedir, "web", "templates")
    static_folder = os.path.join(basedir, "web", "static")
    web_server = WebServer(database, config,
                           meshtastic_connection,
                           telegram_connection,
                           logger,
                           static_folder=static_folder,
                           template_folder=template_folder)
    # non-blocking
    aprs_streamer.run()
    web_server.run()
    telegram_bot.run()
    # blocking
    while True:
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            web_server.shutdown()
            logger.info('Exit requested...')
            sys.exit(0)


if __name__ == '__main__':
    main()

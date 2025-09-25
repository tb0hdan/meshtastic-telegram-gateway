#!/usr/bin/env python3
"""Meshtastic Telegram Gateway"""

#
import argparse
import logging
import os
import signal
import sys
import threading
#
import reverse_geocoder as rg
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration
#
from mtg.bot.meshtastic import MeshtasticBot
from mtg.bot.openai import OpenAIBot
from mtg.bot.telegram import TelegramBot
from mtg.config import Config
from mtg.connection.aprs import APRSStreamer
from mtg.connection.meshtastic import FIFO, FIFO_CMD
from mtg.connection.mqtt import MQTT, MQTTHandler
from mtg.connection.rich import RichConnection
from mtg.connection.telegram import TelegramConnection
from mtg.database import sql_debug, MeshtasticDB
from mtg.filter import CallSignFilter, MeshtasticFilter, TelegramFilter
from mtg.log import setup_logger, LOGFORMAT
from mtg.utils import create_fifo, ExternalPlugins
from mtg.utils.thread_manager import ThreadManager
from mtg.webapp import WebServer
#
from mtg.utils.rf.prefixes import ITUPrefix

def before_send(event, hint):  # pylint:disable=unused-argument
    """
    Check Sentry event before sending it. Remove sensitive data.
    """
    # Remove sensitive data exposure - don't print to stdout
    return event

# pylint:disable=too-many-locals,too-many-statements
def main(args):
    """
    Main function :)

    :return:
    """
    config = Config(config_path=args.config)
    config.read()
    level = logging.INFO
    debug = False
    if config.enforce_type(bool, config.DEFAULT.Debug):
        debug = True
        level = logging.DEBUG
        sql_debug()

    # setup APM
    if config.enforce_type(bool, config.DEFAULT.SentryEnabled):
        sentry_sdk.init(dsn=config.DEFAULT.SentryDSN,
                        debug=debug,
                        traces_sample_rate=1.0,
                        before_send=before_send,
                        integrations=[FlaskIntegration()]
        )
    # warm up reverse cache
    rg.search((50.5, 30.5), verbose=debug)
    # our logger
    logger = setup_logger('mesh', level)
    # meshtastic logger
    logging.basicConfig(level=level,
                        format=LOGFORMAT)
    #
    database = MeshtasticDB(os.path.join(args.basedir, config.Meshtastic.DatabaseFile), logger)
    meshtastic_filter = MeshtasticFilter(database, config, logger)
    #
    telegram_connection = TelegramConnection(config.Telegram.Token, logger)
    meshtastic_connection = RichConnection(config.Meshtastic.Device, logger, config, meshtastic_filter,
                                           database, rg_fn=rg.search)
    database.set_meshtastic(meshtastic_connection)
    meshtastic_connection.connect()
    #
    mqtt_connection = MQTT(config.MQTT.Topic, config.MQTT.Host, config.MQTT.User, config.MQTT.Password,
                           logger, config.enforce_type(int, config.MQTT.Port))
    mqtt_connection.set_config(config)
    mqtt_handler = MQTTHandler(config.MQTT.Topic, logger)
    mqtt_connection.set_handler(mqtt_handler.handler)
    mqtt_handler.set_node_callback(meshtastic_connection.on_mqtt_node)
    #
    itu_prefix = ITUPrefix(logger)
    #
    aprs_streamer = APRSStreamer(config, itu_prefix)
    call_sign_filter = CallSignFilter(database, config, logger)
    aprs_streamer.set_db(database)
    aprs_streamer.set_filter(call_sign_filter)
    aprs_streamer.set_logger(logger)
    aprs_streamer.set_meshtastic(meshtastic_connection)
    aprs_streamer.set_telegram_connection(telegram_connection)
    #
    telegram_bot = TelegramBot(config, meshtastic_connection, telegram_connection)
    telegram_filter = TelegramFilter(database, config, logger)
    telegram_bot.set_aprs(aprs_streamer)
    telegram_bot.set_filter(telegram_filter)
    telegram_bot.set_logger(logger)
    #
    open_ai = OpenAIBot(logger)
    meshtastic_bot = MeshtasticBot(database, config, meshtastic_connection, telegram_connection, open_ai)
    # set filter for MQTT
    mqtt_handler.set_filter(meshtastic_filter)
    meshtastic_bot.set_filter(meshtastic_filter)
    meshtastic_bot.set_logger(logger)
    meshtastic_bot.set_aprs(aprs_streamer)
    meshtastic_bot.subscribe()
    #
    template_folder = os.path.join(args.basedir, "web", "templates")
    static_folder = os.path.join(args.basedir, "web", "static")
    web_server = WebServer(database, config,
                           meshtastic_connection,
                           telegram_connection,
                           logger,
                           static_folder=static_folder,
                           template_folder=template_folder)
    # external plugins
    external_plugins = ExternalPlugins(database, config, meshtastic_connection, telegram_connection, logger)

    # Initialize thread manager for runners with restart functionality
    thread_manager = ThreadManager(logger)

    # Register all runners with the thread manager
    if config is not None and config.enforce_type(bool, config.APRS.Enabled):
        thread_manager.register_runner("APRS Streamer", aprs_streamer,
                                  restart_delay=10.0,
                                  thread_patterns=["APRS Streamer"])
    if config is not None and config.enforce_type(bool, config.Meshtastic.FIFOEnabled):
        thread_manager.register_runner("Meshtastic Connection", meshtastic_connection,
                                  restart_delay=5.0,
                                  thread_patterns=["Meshtastic Connection", "MeshtasticCmd"])
    if config is not None and config.enforce_type(bool, config.WebApp.Enabled):
        thread_manager.register_runner("Web Server", web_server,
                                  restart_delay=5.0,
                                  thread_patterns=['WebApp Server'])
    if config is not None and config.enforce_type(bool, config.MQTT.Enabled):
        thread_manager.register_runner("MQTT Connection", mqtt_connection,
                                  restart_delay=10.0,
                                  thread_patterns=["MQTT Connection"])
    thread_manager.register_runner("External Plugins", external_plugins,
                                  restart_delay=15.0,
                                  thread_patterns=[])

    # Start all managed runners
    thread_manager.start_all()

    # our main loop, blocking
    telegram_bot.run()
    logger.info('Exiting...')
    telegram_bot.shutdown()
    thread_manager.shutdown_all()
    sys.exit(0)


def post2mesh(args):
    """
    post2mesh - send messages from console using Meshtastic networks. For alerts etc

    :return:
    """
    if args.message is None:
        logging.error('Cannot send empty message...')
        return
    create_fifo(FIFO)
    with open(FIFO, 'w', encoding='utf-8') as fifo:
        fifo.write(args.message + '\n')

def post_cmd(args):
    """
    post_cmd - send commands to Meshtastic connection

    :param args:
    :return:
    """
    if args.command is None:
        logging.error('Cannot send empty command...')
        return
    create_fifo(FIFO_CMD)
    with open(FIFO_CMD, 'w', encoding='utf-8') as fifo:
        fifo.write(args.command + '\n')

def cmd(basedir):
    """
    cmd - Run argument parser and process command line parameters

    :return:
    """
    parser = argparse.ArgumentParser()
    subparser = parser.add_subparsers(title="commands", help="commands")

    post = subparser.add_parser("post2mesh", help="site command")
    post.add_argument("-m", "--message", help="message to post to Meshtastic")
    post.set_defaults(func=post2mesh)
    #
    run = subparser.add_parser("run", help="run")
    run.add_argument("-c", "--config", help="path to config", default="./mesh.ini")
    run.add_argument("-b", "--basedir", help="base directory for web files etc", default=basedir)
    run.set_defaults(func=main)
    #
    reboot = subparser.add_parser("command", help="Send command")
    reboot.add_argument("-c", "--command", help="Send command")
    reboot.set_defaults(func=post_cmd)
    #
    argv = sys.argv[1:]
    if len(argv) == 0:
        argv = ['run']
    args = parser.parse_args(argv)
    logging.info(args.func(args))

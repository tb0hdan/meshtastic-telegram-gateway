#!/usr/bin/env python3
"""Meshtastic Telegram Gateway"""

#
import configparser
import logging
import sys
import time
#
from datetime import datetime, timedelta
from threading import Thread
from typing import (
    AnyStr,
    Dict,
    List,
    SupportsInt
)
from urllib.parse import parse_qs
#
import aprslib
import flask
import haversine  # type: ignore
import humanize  # type: ignore
import telegram.ext
#
from flask import Flask, jsonify, make_response, request, render_template
from flask.views import View
from meshtastic import (
    BROADCAST_ADDR as MESHTASTIC_BROADCAST_ADDR,
    serial_interface as meshtastic_serial_interface,
    portnums_pb2 as meshtastic_portnums_pb2
)

from pony.orm import db_session, Database, Optional, PrimaryKey, Required, Set, set_sql_debug
from pubsub import pub
from telegram import Update
from telegram.ext import CallbackContext
from telegram.ext import CommandHandler
from telegram.ext import Updater
from telegram.ext import MessageHandler, Filters
from werkzeug.serving import make_server

# has to be global variable ;-(
DB = Database()
VERSION = open('VERSION', 'r').read().rstrip('\n')


def get_lat_lon_distance(latlon1: tuple, latlon2: tuple) -> float:
    """
    Get distance (in meters) between two geographical points using GPS coordinates

    :param latlon1:
    :param latlon2:
    :return:
    """
    if not isinstance(latlon1, tuple):
        raise RuntimeError('Tuple expected for latlon1')
    if not isinstance(latlon2, tuple):
        raise RuntimeError('Tuple expected for latlon2')
    return haversine.haversine(latlon1, latlon2, unit=haversine.Unit.METERS)


def setup_logger(name=__name__, level=logging.INFO, version=VERSION) -> logging.Logger:
    """
    Set up logger and return usable instance

    :param name:
    :param level:
    :param version:

    :return:
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # create console handler and set level to debug
    handler = logging.StreamHandler()
    handler.setLevel(level)

    # create formatter
    fmt = '%(asctime)s - %(name)s/v{} - %(levelname)s - %(message)s'.format(version)
    formatter = logging.Formatter(fmt)

    # add formatter to ch
    handler.setFormatter(formatter)

    # add ch to logger
    logger.addHandler(handler)
    return logger


class Config:
    """
    Configuration class. Most methods are properties.
    """

    def __init__(self, config_path="mesh.ini"):
        self.config = None
        self.config_path = config_path

    def read(self) -> None:
        """
        Read configuration from file

        :return:
        """
        self.config = configparser.ConfigParser()
        self.config.read(self.config_path)

    @property
    def debug(self) -> bool:
        """
        Debugging enable/disable toggle

        :return:
        """
        value = self.config['DEFAULT']['Debug']
        if value.lower() == 'true':
            return True
        return False

    @property
    def telegram_admin(self) -> AnyStr:
        """
        Admin's Telegram ID

        :return:
        """
        return self.config['Telegram']['Admin']

    @property
    def meshtastic_admin(self) -> AnyStr:
        """
        Admin's Telegram ID

        :return:
        """
        return self.config['Meshtastic']['Admin']

    @property
    def meshtastic_device(self) -> str:
        """
        Meshtastic device path

        :return:
        """
        return self.config['Meshtastic']['Device']

    @property
    def meshtastic_database_file(self) -> AnyStr:
        """
        Meshtastic database file

        :return:
        """
        return self.config['Meshtastic']['DatabaseFile']

    @property
    def meshtastic_room(self) -> AnyStr:
        """
        Meshtastic room

        :return:
        """
        return self.config['Telegram']['Room']

    @property
    def telegram_token(self) -> str:
        """
        Telegram API token

        :return:
        """
        return self.config['Telegram']['Token']

    @property
    def web_app_port(self) -> int:
        """
        Web application port

        :return:
        """
        return int(self.config['WebApp']['Port'])

    @property
    def web_app_api_key(self) -> AnyStr:
        """
        Web application API key. Used by Google Maps Javascript API.

        :return:
        """
        return self.config['WebApp']['APIKey']

    @property
    def web_app_enabled(self) -> bool:
        """
        Web application enable/disable toggle

        :return:
        """
        value = self.config['WebApp']['Enabled']
        if value.lower() == 'true':
            return True
        return False

    @property
    def web_app_center_latitude(self) -> float:
        """
        Web application center coordinate (latitude)

        :return:
        """
        return float(self.config['WebApp']['Center_Latitude'])

    @property
    def web_app_center_longitude(self) -> float:
        """
        Web application center coordinate (longitude)

        :return:
        """
        return float(self.config['WebApp']['Center_Longitude'])

    @property
    def web_app_last_heard_default(self) -> SupportsInt:
        """
        Web application last heard value in seconds

        :return:
        """
        return int(self.config['WebApp']['LastHeardDefault'])

    @property
    def aprs_enabled(self) -> bool:
        """

        :return:
        """
        value = self.config['APRS']['Enabled']
        if value.lower() == 'true':
            return True
        return False

    @property
    def aprs_to_meshtastic_enabled(self) -> bool:
        """

        :return:
        """
        value = self.config['APRS']['ToMeshtastic']
        if value.lower() == 'true':
            return True
        return False

    @property
    def aprs_from_meshtastic_enabled(self) -> bool:
        """

        :return:
        """
        value = self.config['APRS']['FromMeshtastic']
        if value.lower() == 'true':
            return True
        return False

    @property
    def aprs_callsign(self) -> AnyStr:
        """

        :return:
        """
        return self.config['APRS']['Callsign']

    @property
    def aprs_password(self) -> AnyStr:
        """

        :return:
        """
        return self.config['APRS']['Password']


class TelegramConnection:
    """
    Telegram connection
    """

    def __init__(self, token: str, logger: logging.Logger):
        self.logger = logger
        self.updater = Updater(token=token, use_context=True)

    def send_message(self, *args, **kwargs) -> None:
        """
        Send Telegram message

        :param args:
        :param kwargs:
        :return:
        """
        self.updater.bot.send_message(*args, **kwargs)

    def poll(self) -> None:
        """
        Run Telegram bot polling

        :return:
        """
        self.updater.start_polling()

    @property
    def dispatcher(self) -> telegram.ext.Dispatcher:
        """
        Return Telegram dispatcher for commands

        :return:
        """
        return self.updater.dispatcher


class MeshtasticConnection:
    """
    Meshtastic device connection
    """

    def __init__(self, dev_path: str, logger: logging.Logger):
        self.interface = meshtastic_serial_interface.SerialInterface(devPath=dev_path, debugOut=sys.stdout)
        self.logger = logger

    def send_text(self, *args, **kwargs) -> None:
        """
        Send Meshtastic message

        :param args:
        :param kwargs:
        :return:
        """
        self.interface.sendText(*args, **kwargs)

    def node_info(self, node_id) -> Dict:
        """
        Return node information for a specific node ID

        :param node_id:
        :return:
        """
        return self.interface.nodes.get(node_id, {})

    @property
    def nodes(self) -> Dict:
        """
        Return dictionary of nodes

        :return:
        """
        return self.interface.nodes if self.interface.nodes else {}

    @property
    def nodes_with_info(self) -> List:
        """
        Return list of nodes with information

        :return:
        """
        node_list = []
        for node in self.nodes:
            node_list.append(self.nodes.get(node))
        return node_list

    @property
    def nodes_with_position(self) -> List:
        """
        Filter out nodes without position

        :return:
        """
        node_list = []
        for node_info in self.nodes_with_info:
            if not node_info.get('position'):
                continue
            node_list.append(node_info)
        return node_list

    @property
    def nodes_with_user(self) -> List:
        """
        Filter out nodes without position or user

        :return:
        """
        node_list = []
        for node_info in self.nodes_with_position:
            if not node_info.get('user'):
                continue
            node_list.append(node_info)
        return node_list


class MeshtasticNodeRecord(DB.Entity):  # pylint:disable=too-few-public-methods
    """
    MeshtasticNodeRecord: node record representation in DB
    """
    nodeId = PrimaryKey(str)
    nodeName = Required(str)
    lastHeard = Required(datetime)
    hwModel = Required(str)
    locations = Set(lambda: MeshtasticLocationRecord)
    messages = Set(lambda: MeshtasticMessageRecord)


class MeshtasticLocationRecord(DB.Entity):  # pylint:disable=too-few-public-methods
    """
    MeshtasticLocationRecord: location record representation in DB
    """
    datetime = Required(datetime)
    altitude = Required(float)
    batteryLevel = Required(float)
    latitude = Required(float)
    longitude = Required(float)
    rxSnr = Required(float)
    node = Optional(MeshtasticNodeRecord)


class MeshtasticMessageRecord(DB.Entity):  # pylint:disable=too-few-public-methods
    """
    MeshtasticMessageRecord: message record representation in DB
    """
    datetime = Required(datetime)
    message = Required(str)
    node = Optional(MeshtasticNodeRecord)


class MeshtasticFilterRecord(DB.Entity):
    """
    MeshtasticFilterRecord: filter representation in DB
    """
    # meshtastic, telegram, etc...
    connection = Required(str)
    item = Required(str)
    reason = Required(str)
    active = Required(bool)


class MeshtasticDB:
    """
    Meshtastic events database
    """

    def __init__(self, db_file: AnyStr, connection: MeshtasticConnection, logger: logging.Logger):
        self.connection = connection
        self.logger = logger
        DB.bind(provider='sqlite', filename=db_file, create_db=True)
        DB.generate_mapping(create_tables=True)

    @db_session
    def get_node_record(self, node_id: AnyStr) -> MeshtasticNodeRecord:
        """
        Retrieve node record from DB

        :param node_id:
        :return:
        """
        node_record = MeshtasticNodeRecord.select(lambda n: n.nodeId == node_id).first()
        node_info = self.connection.node_info(node_id)
        last_heard = datetime.fromtimestamp(node_info.get('lastHeard', 0))
        if not node_record:
            # create new record
            node_record = MeshtasticNodeRecord(
                nodeId=node_id,
                nodeName=node_info.get('user', {}).get('longName', ''),
                lastHeard=last_heard,
                hwModel=node_info.get('user', {}).get('hwModel', ''),
            )
            return node_record
        # Update lastHeard and return record
        node_record.lastHeard = last_heard  # pylint:disable=invalid-name
        return node_record

    @db_session
    def store_message(self, packet: dict) -> None:
        """
        Store Meshtastic message in DB

        :param packet:
        :return:
        """
        from_id = packet.get("fromId")
        node_record = self.get_node_record(from_id)
        decoded = packet.get('decoded')
        message = decoded.get('text', '')
        # Save meshtastic message
        MeshtasticMessageRecord(
            datetime=datetime.fromtimestamp(time.time()),
            message=message,
            node=node_record,
        )

    @db_session
    def store_location(self, packet: dict) -> None:
        """
        Store Meshtastic location in DB

        :param packet:
        :return:
        """
        from_id = packet.get("fromId")
        node_record = self.get_node_record(from_id)
        # Save location
        position = packet.get('decoded', {}).get('position', {})
        # add location to DB
        MeshtasticLocationRecord(
            datetime=datetime.fromtimestamp(time.time()),
            altitude=position.get('altitude', 0),
            batteryLevel=position.get('batteryLevel', 100),
            latitude=position.get('latitude', 0),
            longitude=position.get('longitude', 0),
            rxSnr=packet.get('rxSnr', 0),
            node=node_record,
        )


class Filter:
    """

    """
    connection_type = ""

    def __init__(self, database: MeshtasticDB, config: Config, connection: MeshtasticConnection,
                 logger: logging.Logger):
        self.db = database
        self.connection = connection
        self.config = config
        self.logger = logger


class TelegramFilter(Filter):
    """

    """
    def __init__(self, database: MeshtasticDB, config: Config, connection: MeshtasticConnection,
                 logger: logging.Logger):
        super().__init__(database, config, connection, logger)
        self.db = database
        self.config = config
        self.connection = connection
        self.connection_type = "Telegram"
        self.logger = logger


class MeshtasticFilter(Filter):
    """

    """
    def __init__(self, database: MeshtasticDB, config: Config, connection: MeshtasticConnection,
                 logger: logging.Logger):
        super().__init__(database, config, connection, logger)
        self.db = database
        self.config = config
        self.connection = connection
        self.connection_type = "Meshtastic"
        self.logger = logger


class CallSignFilter(Filter):
    """

    """
    def __init__(self, database: MeshtasticDB, config: Config, connection: MeshtasticConnection,
                 logger: logging.Logger):
        super().__init__(database, config, connection, logger)
        self.db = database
        self.config = config
        self.connection = connection
        self.connection_type = "Callsign"
        self.logger = logger


class APRSStreamer:
    """

    """
    def __init__(self, config: Config, logger: logging.Logger, call_sign_filter: CallSignFilter):
        self.aprs_is = None
        self.call_sign_filter = call_sign_filter
        self.config = config
        self.logger = logger
        self.exit = False

    def send_packet(self, packet):
        """

        :param packet:
        :return:
        """
        if not self.config.aprs_from_meshtastic_enabled:
            return
        self.aprs_is.sendall(packet)

    def process(self, packet):
        """

        :param packet:
        :return:
        """
        if not self.config.aprs_to_meshtastic_enabled:
            return
        self.logger.debug(packet)

    @staticmethod
    def callback(packet):
        """

        :param packet:
        :return:
        """
        pub.sendMessage('APRS', packet=packet)

    def run_loop(self):
        """

        :return:
        """
        self.aprs_is = aprslib.IS(self.config.aprs_callsign,
                                  self.config.aprs_password,
                                  host='euro.aprs2.net',
                                  port=14580)
        self.aprs_is.set_filter('r/%f/%f/50' % (self.config.web_app_center_latitude,
                                                self.config.web_app_center_longitude))
        while not self.exit:
            try:
                self.aprs_is.connect()
                self.aprs_is.consumer(self.callback, immortal=True)
            except KeyboardInterrupt:
                break
            except aprslib.exceptions.ConnectionDrop:
                self.logger.debug("aprs conn drop")
            except aprslib.exceptions.LoginError:
                self.logger.debug("aprs login error")

    def run(self):
        """

        :return:
        """
        if self.config.aprs_enabled:
            pub.subscribe(self.process, 'APRS')
            thread = Thread(target=self.run_loop, daemon=True)
            thread.start()


class TelegramBot:
    """
    Telegram bot
    """

    def __init__(self, config: Config, meshtastic_connection: MeshtasticConnection,
                 telegram_connection: TelegramConnection, logger: logging.Logger, filter_class: TelegramFilter):
        self.config = config
        self.filter = filter_class
        self.logger = logger
        self.meshtastic_connection = meshtastic_connection
        self.telegram_connection = telegram_connection

        start_handler = CommandHandler('start', self.start)
        node_handler = CommandHandler('nodes', self.nodes)
        dispatcher = self.telegram_connection.dispatcher

        dispatcher.add_handler(start_handler)
        dispatcher.add_handler(node_handler)

        echo_handler = MessageHandler(Filters.text & (~Filters.command), self.echo)
        dispatcher.add_handler(echo_handler)

    def echo(self, update: Update, _) -> None:
        """
        Telegram bot echo handler. Does actual message forwarding

        :param update:
        :param _:
        :return:
        """
        if str(update.effective_chat.id) != str(self.config.meshtastic_room):
            self.logger.debug("%d %s", update.effective_chat.id, self.config.meshtastic_room)
            return
        full_user = update.effective_user.first_name
        if update.effective_user.last_name is not None:
            full_user += ' ' + update.effective_user.last_name
        self.logger.debug("%d %s %s", update.effective_chat.id, full_user, update.message.text)
        self.meshtastic_connection.send_text("%s: %s" % (full_user, update.message.text))

    def poll(self) -> None:
        """
        Telegram bot poller. Uses connection under the hood

        :return:
        """
        self.telegram_connection.poll()

    @staticmethod
    def start(update: Update, context: CallbackContext) -> None:
        """
        Telegram /start command handler.

        :param update:
        :param context:
        :return:
        """
        context.bot.send_message(chat_id=update.effective_chat.id, text="I'm a bot, please talk to me!")

    def nodes(self, update: Update, context: CallbackContext) -> None:
        """
        Returns list of nodes to user

        :param update:
        :param context:
        :return:
        """
        table = self.meshtastic_connection.interface.showNodes(includeSelf=False)
        context.bot.send_message(chat_id=update.effective_chat.id, text=table)


class MeshtasticBot:
    """
    Meshtastic bot
    """

    def __init__(self, db: MeshtasticDB, config: Config, meshtastic_connection: MeshtasticConnection,
                 telegram_connection: TelegramConnection, logger: logging.Logger, filter_class: MeshtasticFilter):
        self.db = db
        self.config = config
        self.filter = filter_class
        self.logger = logger
        self.telegram_connection = telegram_connection
        self.meshtastic_connection = meshtastic_connection
        # track ping request/reply
        self.ping_container = {}

    def on_connection(self, interface, topic=pub.AUTO_TOPIC):
        """
        on radio connection event

        :param interface:
        :param topic:
        :return:
        """
        self.logger.debug("connection on %s topic %s", interface, topic)

    def on_node_info(self, node, interface):
        """
        on node information event

        :param node:
        :param interface:
        :return:
        """
        self.logger.debug("node info %s on interface %s", node, interface)

    def subscribe(self) -> None:
        """
        Subscribe to Meshtastic events

        :return:
        """
        pub.subscribe(self.on_receive, "meshtastic.receive")
        pub.subscribe(self.on_connection, "meshtastic.connection.established")
        pub.subscribe(self.on_connection, "meshtastic.connection.lost")

    @staticmethod
    def process_distance_command(packet, interface) -> None:  # pylint:disable=too-many-locals
        """
        Process /distance Meshtastic command

        :param packet:
        :param interface:
        :return:
        """
        from_id = packet.get('fromId')
        mynode_info = interface.nodes.get(from_id)
        if not mynode_info:
            interface.sendText("distance err: no node info", destinationId=from_id)
            return
        position = mynode_info.get('position', {})
        if not position:
            interface.sendText("distance err: no position", destinationId=from_id)
            return
        my_latitude = position.get('latitude')
        my_longitude = position.get('longitude')
        if not (my_latitude and my_longitude):
            interface.sendText("distance err: no lat/lon", destinationId=from_id)
            return
        for node in interface.nodes:
            node_info = interface.nodes.get(node)
            position = node_info.get('position', {})
            if not position:
                continue
            latitude = position.get('latitude')
            longitude = position.get('longitude')
            if not (latitude and longitude):
                continue
            user = node_info.get('user', {})
            if not user:
                continue
            node_id = user.get('id', '')
            if from_id == node_id:
                continue
            long_name = user.get('longName', '')
            distance = round(get_lat_lon_distance((my_latitude, my_longitude), (latitude, longitude)))
            distance = humanize.intcomma(distance)
            msg = '{}: {}m'.format(long_name, distance)
            interface.sendText(msg, destinationId=from_id)

    def process_ping_command(self, packet, interface) -> None:
        """
        Process /ping Meshtastic command

        :param packet:
        :param interface:
        :return:
        """
        from_id = packet.get('fromId')
        self.ping_container[from_id] = {'timestamp': time.time()}
        payload = str.encode("test string")
        interface.sendData(payload,
                           MESHTASTIC_BROADCAST_ADDR,
                           portNum=meshtastic_portnums_pb2.PortNum.REPLY_APP,
                           wantAck=True, wantResponse=True)

    def process_meshtastic_command(self, packet, interface) -> None:
        """
        Process Meshtastic command

        :param packet:
        :param interface:
        :return:
        """
        decoded = packet.get('decoded')
        from_id = packet.get('fromId')
        msg = decoded.get('text', '')
        if msg.startswith('/distance'):
            self.process_distance_command(packet, interface)
            return
        if msg.startswith('/ping'):
            self.process_ping_command(packet, interface)
            return
        self.meshtastic_connection.send_text("unknown command", destinationId=from_id)

    def process_pong(self, packet):
        """

        :param packet:
        :return:
        """
        from_id = packet.get('fromId')
        to_id = packet.get('toId')
        rx_time = packet.get('rxTime', 0)
        rx_snr = packet.get('rxSnr', 0)
        processing_time = time.time() - rx_time
        # node info
        node_info = self.meshtastic_connection.node_info(to_id)
        user_info = node_info.get('user', {})
        remote_name = user_info.get('longName', to_id)
        #
        if self.ping_container.get(from_id, {}):
            timestamp = self.ping_container[from_id].get('timestamp', 0)
            processing_time += time.time() - timestamp
        msg = "Pong from {} at {:.2f} SNR time={:.3f}s".format(remote_name, rx_snr, processing_time)
        self.meshtastic_connection.send_text(msg, destinationId=from_id)

    def on_receive(self, packet, interface) -> None:
        """
        onReceive is called when a packet arrives

        :param packet:
        :param interface:
        :return:
        """
        self.logger.debug("Received: {}".format(packet))
        to_id = packet.get('toId')
        decoded = packet.get('decoded')
        from_id = packet.get('fromId')
        if decoded.get('portnum') != 'TEXT_MESSAGE_APP':
            # notifications
            if decoded.get('portnum') == 'POSITION_APP':
                self.db.store_location(packet)
                return
            # pong
            if decoded.get('portnum') == 'REPLY_APP':
                self.process_pong(packet)
                return
            # updater.bot.send_message(chat_id=MESHTASTIC_ADMIN, text="%s" % decoded)
            # self.logger.debug(decoded)
            return
        # ignore non-broadcast messages
        if to_id != MESHTASTIC_BROADCAST_ADDR:
            return
        # Save messages
        self.db.store_message(packet)
        # Process commands and forward messages
        node_info = interface.nodes.get(from_id)
        long_name = from_id
        if node_info is not None:
            user_info = node_info.get('user')
            long_name = user_info.get('longName')
        msg = decoded.get('text', '')
        # skip commands
        if msg.startswith('/'):
            self.process_meshtastic_command(packet, interface)
            return
        self.telegram_connection.send_message(chat_id=self.config.meshtastic_room, text="%s: %s" % (long_name, msg))


class RenderTemplateView(View):
    """
    Generic HTML template renderer
    """

    def __init__(self, template_name):
        self.template_name = template_name

    def dispatch_request(self) -> AnyStr:
        """
        Process Flask request

        :return:
        """
        return render_template(self.template_name, timestamp=int(time.time()))


class RenderScript(View):
    """
    Specific script renderer
    """

    def __init__(self, config: Config):
        self.config = config

    def dispatch_request(self) -> flask.Response:
        """
        Process Flask request

        :return:
        """
        response = make_response(render_template("script.js",
                                                 api_key=self.config.web_app_api_key,
                                                 center_latitude=self.config.web_app_center_latitude,
                                                 center_longitude=self.config.web_app_center_longitude,
                                                 ))
        response.headers['Content-Type'] = 'application/javascript'
        return response


class RenderDataView(View):
    """
    Specific data renderer
    """

    def __init__(self, config: Config, meshtastic_connection: MeshtasticConnection, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.meshtastic_connection = meshtastic_connection

    @staticmethod
    def format_hw(hw_model: AnyStr) -> AnyStr:
        """
        Format hardware model

        :param hw_model:
        :return:
        """
        if hw_model == 'TBEAM':
            return '<a href="https://meshtastic.org/docs/hardware/supported/tbeam">TBEAM</a>'
        if hw_model.startswith('TLORA'):
            return '<a href="https://meshtastic.org/docs/hardware/supported/lora">TLORA</a>'
        return hw_model

    def dispatch_request(self) -> flask.Response:  # pylint:disable=too-many-locals
        """
        Process Flask request

        :return:
        """
        query_string = parse_qs(request.query_string)
        tail_value = self.config.web_app_last_heard_default
        #
        tail = query_string.get(b'tail', [])
        if len(tail) > 0:
            try:
                tail_value = int(tail[0].decode())
            except ValueError:
                self.logger.error("Wrong tail value: ", tail)
        #
        name = ''
        name_qs = query_string.get(b'name', [])
        if len(name_qs) > 0:
            name = name_qs[0].decode()
        nodes = []
        for node_info in self.meshtastic_connection.nodes_with_user:
            position = node_info.get('position', {})
            latitude = position.get('latitude')
            longitude = position.get('longitude')
            if not (latitude and longitude):
                continue
            user = node_info.get('user', {})
            hw_model = user.get('hwModel', 'unknown')
            snr = node_info.get('snr', 10.0)
            # No signal info, use default MAX (10.0)
            if snr is None:
                snr = 10.0
            last_heard = int(node_info.get('lastHeard', 0))
            last_heard_dt = datetime.fromtimestamp(last_heard)
            battery_level = position.get('batteryLevel', 100)
            altitude = position.get('altitude', 0)
            # tail filter
            diff = datetime.fromtimestamp(time.time()) - last_heard_dt
            if diff > timedelta(seconds=tail_value):
                continue
            # name filter
            if len(name) > 0 and user.get('longName') != name:
                continue
            #
            nodes.append([user.get('longName'), str(round(latitude, 5)),
                          str(round(longitude, 5)), self.format_hw(hw_model), snr,
                          last_heard_dt.strftime("%d/%m/%Y, %H:%M:%S"),
                          battery_level,
                          altitude,
                          ])
        return jsonify(nodes)


class WebApp:  # pylint:disable=too-few-public-methods
    """
    WebApp: web application container
    """

    def __init__(self, app: Flask, config: Config, meshtastic_connection: MeshtasticConnection, logger: logging.Logger):
        self.app = app
        self.config = config
        self.logger = logger
        self.meshtastic_connection = meshtastic_connection

    def register(self) -> None:
        """
        Register Flask routes

        :return:
        """
        self.app.add_url_rule('/script.js', view_func=RenderScript.as_view(
            'script_page', config=self.config))
        self.app.add_url_rule('/data.json', view_func=RenderDataView.as_view(
            'data_page', config=self.config, meshtastic_connection=self.meshtastic_connection, logger=self.logger))
        # Index pages
        self.app.add_url_rule('/', view_func=RenderTemplateView.as_view(
            'root_page', template_name='index.html'))
        self.app.add_url_rule('/index.htm', view_func=RenderTemplateView.as_view(
            'index_page', template_name='index.html'))
        self.app.add_url_rule('/index.html', view_func=RenderTemplateView.as_view(
            'index_html_page', template_name='index.html'))


class ServerThread(Thread):
    """

    """
    def __init__(self, app: Flask, config: Config, logger: logging.Logger):
        Thread.__init__(self)
        self.config = config
        self.logger = logger
        self.server = make_server('', self.config.web_app_port, app)
        self.ctx = app.app_context()
        self.ctx.push()

    def run(self) -> None:
        """

        :return:
        """
        self.logger.info('starting server')
        self.server.serve_forever()

    def shutdown(self) -> None:
        """

        :return:
        """
        self.server.shutdown()


class WebServer:  # pylint:disable=too-few-public-methods
    """
    Web server wrapper around Flask app
    """

    def __init__(self, config: Config, meshtastic_connection: MeshtasticConnection, logger: logging.Logger):
        self.meshtastic_connection = meshtastic_connection
        self.config = config
        self.logger = logger
        self.app = Flask(__name__)
        self.server = None

    def run(self) -> None:
        """
        Run web server

        :return:
        """
        if self.config.web_app_enabled:
            web_app = WebApp(self.app, self.config, self.meshtastic_connection, self.logger)
            web_app.register()
            self.server = ServerThread(self.app, self.config, self.logger)
            self.server.start()

    def shutdown(self) -> None:
        self.server.shutdown()


if __name__ == '__main__':
    config = Config()
    config.read()
    level = logging.INFO
    if config.debug:
        level = logging.DEBUG
        set_sql_debug(True)

    # our logger
    logger = setup_logger('mesh', level, VERSION)
    # meshtastic logger
    logging.basicConfig(level=level,
                        format='%(levelname)s file:%(filename)s %(funcName)s line:%(lineno)s %(message)s')
    #
    telegram_connection = TelegramConnection(config.telegram_token, logger)
    meshtastic_connection = MeshtasticConnection(config.meshtastic_device, logger)
    database = MeshtasticDB(config.meshtastic_database_file, meshtastic_connection, logger)
    # Initialize filters (node, user, etc)
    call_sign_filter = CallSignFilter(database, config, meshtastic_connection, logger)
    telegram_filter = TelegramFilter(database, config, meshtastic_connection, logger)
    meshtastic_filter = MeshtasticFilter(database, config, meshtastic_connection, logger)
    #
    aprs_streamer = APRSStreamer(config, logger, call_sign_filter)
    telegram_bot = TelegramBot(config, meshtastic_connection, telegram_connection, logger, telegram_filter)
    meshtastic_bot = MeshtasticBot(database, config, meshtastic_connection, telegram_connection, logger,
                                   meshtastic_filter)
    meshtastic_bot.subscribe()
    web_server = WebServer(config, meshtastic_connection, logger)
    # non-blocking
    aprs_streamer.run()
    web_server.run()
    # blocking
    try:
        telegram_bot.poll()
    except KeyboardInterrupt:
        web_server.shutdown()
        logger.info('Exit requested...')
        sys.exit(0)


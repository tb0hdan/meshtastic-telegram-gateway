#!/usr/bin/env python3
"""Meshtastic Telegram Gateway"""

#
import configparser
import time
#
from datetime import datetime
from threading import Thread
#
import haversine
import humanize
import meshtastic.serial_interface
#
from flask import Flask, jsonify, render_template
from flask.views import View
from pony.orm import db_session, Database, Optional, PrimaryKey, Required, select, Set, set_sql_debug
from pubsub import pub
from telegram import Update
from telegram.ext import CallbackContext
from telegram.ext import CommandHandler
from telegram.ext import Updater
from telegram.ext import MessageHandler, Filters

# has to be global variable ;-(
db = Database()


def get_lat_lon_distance(latlon1: tuple, latlon2: tuple) -> float:
    """
    Get distance (in meters) between two geographical points using GPS coordinates

    :param latlon1:
    :param latlon2:
    :return:
    """
    if type(latlon1) != tuple:
        raise RuntimeError('Tuple expected for latlon1')
    if type(latlon2) != tuple:
        raise RuntimeError('Tuple expected for latlon2')
    return haversine.haversine(latlon1, latlon2, unit=haversine.Unit.METERS)


class Config:
    def __init__(self, configPath="mesh.ini"):
        self.config_path = configPath

    def read(self):
        self.config = configparser.ConfigParser()
        self.config.read(self.config_path)

    @property
    def Debug(self):
        return self.config['DEFAULT']['Debug']

    @property
    def MeshtasticAdmin(self):
        return self.config['Telegram']['Admin']

    @property
    def MeshtasticDevice(self):
        return self.config['Meshtastic']['Device']

    @property
    def MeshtasticDatabaseFile(self):
        return self.config['Meshtastic']['DatabaseFile']

    @property
    def MeshtasticRoom(self):
        return self.config['Telegram']['Room']

    @property
    def TelegramToken(self):
        return self.config['Telegram']['Token']

    @property
    def WebappPort(self):
        return self.config['WebApp']['Port']

    @property
    def WebappAPIKey(self):
        return self.config['WebApp']['APIKey']

    @property
    def WebappEnabled(self):
        return self.config['WebApp']['Enabled']

    @property
    def WebappCenterLatitude(self):
        return self.config['WebApp']['Center_Latitude']

    @property
    def WebappCenterLongitude(self):
        return self.config['WebApp']['Center_Longitude']


class TelegramConnection:
    def __init__(self, token: str):
        self.updater = Updater(token=token, use_context=True)

    def send_message(self, *args, **kwargs):
        self.updater.bot.send_message(*args, **kwargs)

    def poll(self):
        self.updater.start_polling()

    @property
    def dispatcher(self):
        return self.updater.dispatcher


class MeshtasticConnection:
    def __init__(self, devPath: str):
        # By default will try to find a meshtastic device, otherwise provide a device path like /dev/ttyUSB0
        self.interface = meshtastic.serial_interface.SerialInterface(devPath=devPath)

    def sendText(self, *args, **kwargs):
        self.interface.sendText(*args, **kwargs)

    def node_info(self, node_id):
        return self.interface.nodes.get(node_id)

    @property
    def nodes(self):
        return self.interface.nodes if self.interface.nodes else []

    @property
    def nodes_with_info(self):
        node_list = []
        for node in self.nodes:
            node_list.append(self.nodes.get(node))
        return node_list

    @property
    def nodes_with_position(self):
        node_list = []
        for nodeInfo in self.nodes_with_info:
            if not nodeInfo.get('position'):
                continue
            node_list.append(nodeInfo)
        return node_list

    @property
    def nodes_with_user(self):
        node_list = []
        for nodeInfo in self.nodes_with_position:
            if not nodeInfo.get('user'):
                continue
            node_list.append(nodeInfo)
        return node_list


class TelegramBot:
    def __init__(self, config: Config, meshtasticConnection: MeshtasticConnection,
                 telegramConnection: TelegramConnection):
        self.config = config
        self.telegramConnection = telegramConnection
        self.meshtasticConnection = meshtasticConnection
        start_handler = CommandHandler('start', self.start)
        node_handler = CommandHandler('nodes', self.nodes)

        dispatcher = self.telegramConnection.dispatcher

        dispatcher.add_handler(start_handler)
        dispatcher.add_handler(node_handler)

        echo_handler = MessageHandler(Filters.text & (~Filters.command), self.echo)
        dispatcher.add_handler(echo_handler)

    def echo(self, update: Update, context: CallbackContext):
        if str(update.effective_chat.id) != str(self.config.MeshtasticRoom):
            print(update.effective_chat.id, self.config.MeshtasticRoom)
            return
        full_user = update.effective_user.first_name
        if update.effective_user.last_name is not None:
            full_user += ' ' + update.effective_user.last_name
        print(update.effective_chat.id, full_user, update.message.text)
        self.meshtasticConnection.sendText("%s: %s" % (full_user, update.message.text))

    def poll(self):
        self.telegramConnection.poll()

    @staticmethod
    def start(update: Update, context: CallbackContext):
        context.bot.send_message(chat_id=update.effective_chat.id, text="I'm a bot, please talk to me!")

    def nodes(self, update: Update, context: CallbackContext):
        table = self.meshtasticConnection.interface.showNodes(includeSelf=False)
        context.bot.send_message(chat_id=update.effective_chat.id, text=table)


class MeshtasticNodeRecord(db.Entity):
    nodeId = PrimaryKey(str)
    nodeName = Required(str)
    lastHeard = Required(datetime)
    hwModel = Required(str)
    locations = Set(lambda: MeshtasticLocationRecord)
    messages = Set(lambda: MeshtasticMessageRecord)


class MeshtasticLocationRecord(db.Entity):
    datetime = Required(datetime)
    altitude = Required(float)
    batteryLevel = Required(float)
    latitude = Required(float)
    longitude = Required(float)
    rxSnr = Required(float)
    node = Optional(MeshtasticNodeRecord)


class MeshtasticMessageRecord(db.Entity):
    datetime = Required(datetime)
    message = Required(str)
    node = Optional(MeshtasticNodeRecord)


class MeshtasticDB:
    def __init__(self, db_file: str, connection: MeshtasticConnection):
        super().__init__()
        self.connection = connection
        db.bind(provider='sqlite', filename=db_file, create_db=True)
        db.generate_mapping(create_tables=True)

    @db_session
    def getNodeRecord(self, nodeId: str):
        nodeRecord = MeshtasticNodeRecord.select(lambda n: n.nodeId == nodeId).first()
        nodeInfo = self.connection.node_info(nodeId)
        lastHeard = datetime.fromtimestamp(nodeInfo.get('lastHeard', 0))
        if not nodeRecord:
            # create new record
            nodeRecord = MeshtasticNodeRecord(
                nodeId=nodeId,
                nodeName=nodeInfo.get('user', {}).get('longName', ''),
                lastHeard=lastHeard,
                hwModel=nodeInfo.get('user', {}).get('hwModel', ''),
            )
            return nodeRecord
        # Update lastHeard and return record
        nodeRecord.lastHeard = lastHeard
        return nodeRecord

    @db_session
    def storeMessage(self, packet: dict):
        fromId = packet.get("fromId")
        nodeRecord = self.getNodeRecord(fromId)
        decoded = packet.get('decoded')
        message = decoded.get('text', '')
        # Save meshtastic message
        MeshtasticMessageRecord(
            datetime=datetime.fromtimestamp(time.time()),
            message=message,
            node=nodeRecord,
        )

    @db_session
    def storeLocation(self, packet: dict):
        fromId = packet.get("fromId")
        nodeRecord = self.getNodeRecord(fromId)
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
            node=nodeRecord,
        )


class MeshtasticBot(MeshtasticDB):
    def __init__(self, config: Config, meshtasticConnection: MeshtasticConnection,
                 telegramConnection: TelegramConnection):
        super().__init__(config.MeshtasticDatabaseFile, meshtasticConnection)
        self.config = config
        self.telegramConnection = telegramConnection
        self.meshtasticConnection = meshtasticConnection
        self.telegramBot = telegramBot
        pub.subscribe(self.onReceive, "meshtastic.receive")
        pub.subscribe(self.onConnection, "meshtastic.connection.established")
        pub.subscribe(self.onNodeInfo, "meshtastic.node.updated")

    def processDistanceCommand(self, packet, interface):
        fromId = packet.get('fromId')
        mynodeInfo = interface.nodes.get(fromId)
        if not mynodeInfo:
            interface.sendText("distance err: no node info", destinationId=fromId)
            return
        position = mynodeInfo.get('position', {})
        if not position:
            interface.sendText("distance err: no position", destinationId=fromId)
            return
        mylatitude = position.get('latitude')
        mylongitude = position.get('longitude')
        if not (mylatitude and mylongitude):
            interface.sendText("distance err: no lat/lon", destinationId=fromId)
            return
        for node in interface.nodes:
            nodeInfo = interface.nodes.get(node)
            position = nodeInfo.get('position', {})
            if not position:
                continue
            latitude = position.get('latitude')
            longitude = position.get('longitude')
            if not (latitude and longitude):
                continue
            user = nodeInfo.get('user', {})
            if not user:
                continue
            nodeId = user.get('id', '')
            if fromId == nodeId:
                continue
            longName = user.get('longName', '')
            distance = round(get_lat_lon_distance((mylatitude, mylongitude), (latitude, longitude)))
            distance = humanize.intcomma(distance)
            msg = '{}: {}m'.format(longName, distance)
            interface.sendText(msg, destinationId=fromId)

    def processMeshtasticCommand(self, packet, interface):
        decoded = packet.get('decoded')
        fromId = packet.get('fromId')
        msg = decoded.get('text', '')
        if msg.startswith('/distance'):
            self.processDistanceCommand(packet, interface)
            return
        interface.sendText("unknown command", destinationId=fromId)

    def onReceive(self, packet, interface):  # called when a packet arrives
        print(f"Received: {packet}")
        toId = packet.get('toId')
        if toId != '^all':
            return
        decoded = packet.get('decoded')
        fromId = packet.get('fromId')
        if decoded.get('portnum') != 'TEXT_MESSAGE_APP':
            # notifications
            if decoded.get('portnum') == 'POSITION_APP':
                self.storeLocation(packet)
                return
            # updater.bot.send_message(chat_id=MESHTASTIC_ADMIN, text="%s" % decoded)
            print(decoded)
            return
        # Save messages
        self.storeMessage(packet)
        # Process commands and forward messages
        nodeInfo = interface.nodes.get(fromId)
        longName = fromId
        if nodeInfo is not None:
            userInfo = nodeInfo.get('user')
            longName = userInfo.get('longName')
        msg = decoded.get('text', '')
        # skip commands
        if msg.startswith('/'):
            self.processMeshtasticCommand(packet, interface)
            return
        self.telegramConnection.send_message(chat_id=self.config.MeshtasticRoom, text="%s: %s" % (longName, msg))

    def onConnection(self, interface, topic=pub.AUTO_TOPIC):  # called when we (re)connect to the radio
        # defaults to broadcast, specify a destination ID if you wish
        # interface.sendText("hello mesh")
        pass

    def onNodeInfo(self, node, interface):
        # updater.bot.send_message(chat_id=MESHTASTIC_ADMIN, text="%s" % node)
        pass


class RenderTemplateView(View):
    def __init__(self, template_name):
        self.template_name = template_name

    def dispatch_request(self):
        return render_template(self.template_name, timestamp=int(time.time()))


class RenderScript(View):
    def __init__(self, config: Config):
        self.config = config

    def dispatch_request(self):
        return render_template("script.js",
                               api_key=self.config.WebappAPIKey,
                               center_latitude=self.config.WebappCenterLatitude,
                               center_longitude=self.config.WebappCenterLongitude,
                               )


class RenderDataView(View):
    def __init__(self, meshtasticConnection: MeshtasticConnection):
        self.meshtasticConnection = meshtasticConnection

    @staticmethod
    def format_hw(hwModel: str):
        if hwModel == 'TBEAM':
            return '<a href="https://meshtastic.org/docs/hardware/supported/tbeam">TBEAM</a>'
        if hwModel.startswith('TLORA'):
            return '<a href="https://meshtastic.org/docs/hardware/supported/lora">TLORA</a>'
        return hwModel

    def dispatch_request(self):
        nodes = []
        for nodeInfo in self.meshtasticConnection.nodes_with_user:
            position = nodeInfo.get('position', {})
            latitude = position.get('latitude')
            longitude = position.get('longitude')
            if not (latitude and longitude):
                continue
            user = nodeInfo.get('user', {})
            hwModel = user.get('hwModel', 'unknown')
            snr = nodeInfo.get('snr', 10.0)
            lastHeard = nodeInfo.get('lastHeard', 0)
            batteryLevel = position.get('batteryLevel', 100)
            altitude = position.get('altitude', 0)
            nodes.append([user.get('longName'), str(round(latitude, 5)),
                          str(round(longitude, 5)), self.format_hw(hwModel), snr,
                          datetime.fromtimestamp(lastHeard).strftime("%d/%m/%Y, %H:%M:%S"),
                          batteryLevel,
                          altitude,
                          ])
        return jsonify(nodes)


class WebApp:
    def __init__(self, app: Flask, config: Config, meshtasticConnection: MeshtasticConnection):
        self.app = app
        self.config = config
        self.meshtasticConnection = meshtasticConnection

    def register(self):
        self.app.add_url_rule('/script.js', view_func=RenderScript.as_view(
            'script_page', config=self.config))
        self.app.add_url_rule('/data.json', view_func=RenderDataView.as_view(
            'data_page', meshtasticConnection=self.meshtasticConnection))
        # Index pages
        self.app.add_url_rule('/', view_func=RenderTemplateView.as_view(
            'root_page', template_name='index.html'))
        self.app.add_url_rule('/index.htm', view_func=RenderTemplateView.as_view(
            'index_page', template_name='index.html'))
        self.app.add_url_rule('/index.html', view_func=RenderTemplateView.as_view(
            'index_html_page', template_name='index.html'))


class WebServer:
    def __init__(self, config: Config, meshtasticConnection: MeshtasticConnection):
        self.meshtasticConnection = meshtasticConnection
        self.config = config
        self.app = Flask(__name__)

    def run(self):
        if self.config.WebappEnabled:
            webApp = WebApp(self.app, self.config, self.meshtasticConnection)
            webApp.register()
            t = Thread(target=self.app.run, kwargs={'port': self.config.WebappPort})
            t.start()


if __name__ == '__main__':
    config = Config()
    config.read()
    if config.Debug:
        set_sql_debug(True)
    telegramConnection = TelegramConnection(config.TelegramToken)
    meshtasticConnection = MeshtasticConnection(config.MeshtasticDevice)
    telegramBot = TelegramBot(config, meshtasticConnection, telegramConnection)
    meshtasticBot = MeshtasticBot(config, meshtasticConnection, telegramConnection)
    webServer = WebServer(config, meshtasticConnection)
    # non-blocking
    webServer.run()
    # blocking
    telegramBot.poll()

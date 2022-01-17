#!/usr/bin/env python3

import configparser
import time

from datetime import datetime
from threading import Thread
#
from flask import Flask, jsonify, render_template
from flask_headers import headers
import haversine
import humanize

app = Flask(__name__)

config = configparser.ConfigParser()
config.read('mesh.ini')

import meshtastic
import time
import meshtastic.serial_interface
from pubsub import pub
#
from telegram import Update
from telegram.ext import CallbackContext
from telegram.ext import CommandHandler
from telegram.ext import Updater
from telegram.ext import MessageHandler, Filters


MESHTASTIC_ADMIN = config['Telegram']['Admin']
MESHTASTIC_ROOM = config['Telegram']['Room']
TELEGRAM_TOKEN = config['Telegram']['Token']
WEBAPP_PORT = config['WebApp']['Port']
WEBAPP_APIKEY = config['WebApp']['APIKey']
WEBAPP_ENABLED = config['WebApp']['Enabled']

interface = None


def echo(update: Update, context: CallbackContext):
    if str(update.effective_chat.id) != str(MESHTASTIC_ROOM):
        print(update.effective_chat.id, MESHTASTIC_ROOM)
        return
    full_user = update.effective_user.first_name
    if update.effective_user.last_name is not None:
        full_user += ' ' + update.effective_user.last_name
    print(update.effective_chat.id, full_user, update.message.text)
    if interface is not None:
        interface.sendText("%s: %s" % (full_user, update.message.text))

def start(update: Update, context: CallbackContext):
    context.bot.send_message(chat_id=update.effective_chat.id, text="I'm a bot, please talk to me!")

def nodes(update: Update, context: CallbackContext):
    table = interface.showNodes(includeSelf=False)
    context.bot.send_message(chat_id=update.effective_chat.id, text=table)

updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
start_handler = CommandHandler('start', start)
node_handler = CommandHandler('nodes', nodes)

dispatcher = updater.dispatcher

dispatcher.add_handler(start_handler)
dispatcher.add_handler(node_handler)

echo_handler = MessageHandler(Filters.text & (~Filters.command), echo)
dispatcher.add_handler(echo_handler)


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


def processDistanceCommand(packet, interface):
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


def processMeshtasticCommand(packet, interface):
    toId = packet.get('toId')
    if toId != '^all':
        return
    decoded = packet.get('decoded')
    fromId = packet.get('fromId')
    if decoded.get('portnum') != 'TEXT_MESSAGE_APP':
        # notifications
        if decoded.get('portnum') == 'POSITION_APP':
            return
        #updater.bot.send_message(chat_id=MESHTASTIC_ADMIN, text="%s" % decoded)
        print(decoded)
        return
    msg = decoded.get('text', '')
    if msg.startswith('/distance'):
        processDistanceCommand(packet, interface)
        return
    interface.sendText("unknown command", destinationId=fromId)

##
def onReceive(packet, interface): # called when a packet arrives
    print(f"Received: {packet}")
    toId = packet.get('toId')
    if toId != '^all':
        return
    decoded = packet.get('decoded')
    fromId = packet.get('fromId')
    if decoded.get('portnum') != 'TEXT_MESSAGE_APP':
        # notifications
        if decoded.get('portnum') == 'POSITION_APP':
            return
        #updater.bot.send_message(chat_id=MESHTASTIC_ADMIN, text="%s" % decoded)
        print(decoded)
        return
    nodeInfo = interface.nodes.get(fromId)
    longName = fromId
    if nodeInfo is not None:
        userInfo = nodeInfo.get('user')
        longName = userInfo.get('longName')
    msg = decoded.get('text', '')
    # skip commands
    if msg.startswith('/'):
        processMeshtasticCommand(packet, interface)
        return
    updater.bot.send_message(chat_id=MESHTASTIC_ROOM, text="%s: %s" % (longName, msg))

def onConnection(interface, topic=pub.AUTO_TOPIC): # called when we (re)connect to the radio
    # defaults to broadcast, specify a destination ID if you wish
    #interface.sendText("hello mesh")
    pass

def onNodeInfo(node, interface):
    #updater.bot.send_message(chat_id=MESHTASTIC_ADMIN, text="%s" % node)
    pass

pub.subscribe(onReceive, "meshtastic.receive")
pub.subscribe(onConnection, "meshtastic.connection.established")
pub.subscribe(onNodeInfo, "meshtastic.node.updated")
# By default will try to find a meshtastic device, otherwise provide a device path like /dev/ttyUSB0
interface = meshtastic.serial_interface.SerialInterface(devPath=config['Meshtastic']['Device'])


def format_hw(hwModel: str):
    if hwModel == 'TBEAM':
        return '<a href="https://meshtastic.org/docs/hardware/supported/tbeam">TBEAM</a>'
    if hwModel.startswith('TLORA'):
        return '<a href="https://meshtastic.org/docs/hardware/supported/lora">TLORA</a>'
    return hwModel

@app.route("/")
def index_page():
    return render_template("index.html", timestamp=int(time.time()))

@app.route("/script.js")
@headers({'Content-Type': 'application/javascript'})
def render_script():
    return render_template("script.js", api_key=WEBAPP_APIKEY)

@app.route("/data.json")
def meshtastic_nodes():
    nodes = []
    if not (interface and interface.nodes):
        return jsonify(nodes)
    for node in interface.nodes:
        nodeInfo = interface.nodes.get(node)
        #
        print(nodeInfo)
        #
        position = nodeInfo.get('position', {})
        if not position:
            continue
        user = nodeInfo.get('user', {})
        if not user:
            continue
        latitude = position.get('latitude')
        longitude = position.get('longitude')
        if not (latitude and longitude):
            continue
        hwModel = user.get('hwModel', 'unknown')
        snr = nodeInfo.get('snr', 10.0)
        lastHeard = nodeInfo.get('lastHeard', 0)
        batteryLevel = position.get('batteryLevel', 100)
        altitude = position.get('altitude', 0)
        nodes.append([user.get('longName'), str(round(latitude, 5)),
                      str(round(longitude, 5)), format_hw(hwModel), snr,
                      datetime.fromtimestamp(lastHeard).strftime("%d/%m/%Y, %H:%M:%S"),
                      batteryLevel,
                      altitude,
        ])
    return jsonify(nodes)

if WEBAPP_ENABLED:
    t = Thread(target=app.run, kwargs={'port':WEBAPP_PORT})
    t.start()

print('Reached updater.start_polling()')
# blocking call
updater.start_polling()

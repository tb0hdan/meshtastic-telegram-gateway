#!/usr/bin/env python3

import configparser

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

interface = None


def echo(update: Update, context: CallbackContext):
    if update.effective_chat.id != MESHTASTIC_ROOM:
        #print(update.effective_chat.id)
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
    updater.bot.send_message(chat_id=MESHTASTIC_ROOM, text="%s: %s" % (longName, decoded.get('text')))

def onConnection(interface, topic=pub.AUTO_TOPIC): # called when we (re)connect to the radio
    # defaults to broadcast, specify a destination ID if you wish
    #interface.sendText("hello mesh")
    pass

def onNodeInfo(node, interface):
    #updater.bot.send_message(chat_id=MESHTASTIC_ADMIN, text="%s" % node)
    print(node)

pub.subscribe(onReceive, "meshtastic.receive")
pub.subscribe(onConnection, "meshtastic.connection.established")
pub.subscribe(onNodeInfo, "meshtastic.node.updated")
# By default will try to find a meshtastic device, otherwise provide a device path like /dev/ttyUSB0
interface = meshtastic.serial_interface.SerialInterface(devPath=config['Meshtastic']['Device'])


updater.start_polling()

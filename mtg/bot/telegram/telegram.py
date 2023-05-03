# -*- coding: utf-8 -*-
""" Telegram bot module """
import requests

import json
import functools
import logging
import os
import pkg_resources
import tempfile
import time
import subprocess
#
from threading import Thread
#
import humanize
import pyqrcode
# pylint:disable=no-name-in-module
from setproctitle import setthreadtitle
from telegram import Update
from telegram.ext import CallbackContext
from telegram.ext import CommandHandler
from telegram.ext import MessageHandler, Filters
#
from mtg.config import Config
from mtg.connection.rich import RichConnection
from mtg.connection.telegram import TelegramConnection
from mtg.filter import TelegramFilter
from mtg.log import VERSION
from mtg.utils import split_message


def check_room(func):
    """
    check_room - decorator to check if bot is in rooms

    :param func:
    :return:
    """

    @functools.wraps(func)
    def wrapper(*args):
        """
        wrapper - decorator wrapper functions
        """
        bot = args[0]
        update = args[1]
        rooms = [bot.config.enforce_type(int, bot.config.Telegram.NotificationsRoom),
                 bot.config.enforce_type(int, bot.config.Telegram.Room)]
        bot_in_rooms = bot.config.enforce_type(bool, bot.config.Telegram.BotInRooms)
        # check rooms
        if update.effective_chat.id in rooms and not bot_in_rooms:
            return None
        # check blacklist as well
        if bot.filter.banned(str(update.effective_user.id)):
            bot.logger.debug(f"User {update.effective_user.id} is in a blacklist...")
            return None
        return func(*args)

    return wrapper


class TelegramBot:
    """
    Telegram bot
    """

    def __init__(self, config: Config, meshtastic_connection: RichConnection,  # pylint:disable=too-many-locals
                 telegram_connection: TelegramConnection):
        self.config = config
        self.filter = None
        self.logger = None
        self.meshtastic_connection = meshtastic_connection
        self.telegram_connection = telegram_connection
        self.name = 'Telegram Bot'

        start_handler = CommandHandler('start', self.start)
        node_handler = CommandHandler('nodes', self.nodes)
        reboot_handler = CommandHandler('reboot', self.reboot)
        uptime_handler = CommandHandler('uptime', self.uptime)
        qr_handler = CommandHandler('qr', self.qr_code)
        ch_handler = CommandHandler('ch', self.channel_url)
        maplink_handler = CommandHandler('map', self.map_link)
        resetdb_handler = CommandHandler('reset_db', self.reset_db)
        traceroute_handler = CommandHandler('traceroute', self.traceroute)
        routes_handler = CommandHandler('routes', self.routes)
        tempo_handler =  CommandHandler('tempo', self.tempo)
        update_handler =  CommandHandler('update', self.update)



        dispatcher = self.telegram_connection.dispatcher

        dispatcher.add_handler(start_handler)
        dispatcher.add_handler(node_handler)
        dispatcher.add_handler(reboot_handler)
        dispatcher.add_handler(qr_handler)
        dispatcher.add_handler(ch_handler)
        dispatcher.add_handler(uptime_handler)
        dispatcher.add_handler(maplink_handler)
        dispatcher.add_handler(resetdb_handler)
        dispatcher.add_handler(traceroute_handler)
        dispatcher.add_handler(routes_handler)
        dispatcher.add_handler(tempo_handler)
        dispatcher.add_handler(update_handler)

        echo_handler = MessageHandler(~Filters.command, self.echo)
        dispatcher.add_handler(echo_handler)

    def set_logger(self, logger: logging.Logger):
        """
        Set class logger

        :param logger:
        :return:
        """
        self.logger = logger

    def set_filter(self, filter_class: TelegramFilter):
        """
        Set filter class

        :param filter_class:
        :return:
        """
        self.filter = filter_class

    def echo(self, update: Update, _) -> None:
        """
        Telegram bot echo handler. Does actual message forwarding

        :param update:
        :param _:
        :return:
        """
        if update.effective_chat.id != self.config.enforce_type(int, self.config.Telegram.Room):
            self.logger.debug("%d %s",
                              update.effective_chat.id,
                              self.config.enforce_type(int, self.config.Telegram.Room))
            return
        if self.filter.banned(str(update.effective_user.id)):
            self.logger.debug(f"User {update.effective_user.id} is in a blacklist...")
            return
        #
        full_user = update.effective_user.first_name
        if update.effective_user.last_name is not None:
            full_user += f' {update.effective_user.last_name}'
        message = ''
        if update.message and update.message.text:
            message += update.message.text

        if update.message and update.message.sticker:
            message += f"sent sticker {update.message.sticker.set_name}: {update.message.sticker.emoji}"

        # check if we got our message
        if not message:
            return
        self.logger.debug(f"{update.effective_chat.id} {full_user} {message}")
        self.meshtastic_connection.send_text(f"{full_user}: {message}")

    def poll(self) -> None:
        """
        Telegram bot poller. Uses connection under the hood

        :return:
        """
        setthreadtitle(self.name)
        self.telegram_connection.poll()

    @check_room
    def start(self, update: Update, context: CallbackContext) -> None:
        """
        Telegram /start command handler.

        :param update:
        :param context:
        :return:
        """
        chat_id = update.effective_chat.id
        self.logger.info(f"Got /start from {chat_id}")
        context.bot.send_message(chat_id=chat_id, text="I'm a bot, please talk to me!")

    @check_room


    def tempo(self, update: Update, context: CallbackContext) -> None:
        """
        Telegram /tempo command handler.

        :param update:
        :param context:
        :return:
        """
        chat_id = update.effective_chat.id
        os.system('/usr/bin/python3 /home/meshtasticpt/scripts/meteo/all.py > /tmp/tempo.txt')
        os.system ('/usr/bin/cat /tmp/tempo.txt')

        out2 = subprocess.check_output(["/usr/bin/cat /tmp/tempo.txt"], shell=True)
        out2 = ou2.decode('utf-8')
        print(type(out2))
    #    try:
    #		encoded = out2.encode('utf-8')
   # 		print(encoded) # 👉️ b'bobbyhadz.com'
    #		print(type(encoded))  # 👉️ <class 'bytes'>
#	except AttributeError:
 #   		pass
        def json_serializer(obj):
            if isinstance(obj, bytes):
               return obj.decode('utf-8')

            return obj


        json_str = json.dumps(out2, default=json_serializer)

        print(json_str)  # "hello world"
        print(type(json_str))  # <class 'str'>
        print('DOne')

#        proc = subprocess.Popen(['/usr/bin/cat', '/tmp/tempo.txt'],stdout=subprocess.PIPE, shell=True)
#        (out, err) = proc.communicate()
#        print("program output:", out)
 

        self.logger.info(f"Got /tempo from {chat_id}")
        context.bot.send_message(chat_id=chat_id, text=json_str)
        context.bot.send_message(chat_id=chat_id, text=type(json_str))

    @check_room

    def reboot(self, update: Update, context: CallbackContext) -> None:
        """
        Telegram reboot command

        :param update:
        :param context:
        :return:
        """
        if update.effective_chat.id != self.config.enforce_type(int, self.config.Telegram.Admin):
            self.logger.info("Reboot requested by non-admin: %d", update.effective_chat.id)
            return
        context.bot.send_message(chat_id=update.effective_chat.id, text="Requesting reboot...")
        self.meshtastic_connection.reboot()

    @check_room
    def reset_db(self, update: Update, context: CallbackContext) -> None:
        """
        Telegram reset node DB command

        :param update:
        :param context:
        :return:
        """
        if update.effective_chat.id != self.config.enforce_type(int, self.config.Telegram.Admin):
            self.logger.info("Reset node DB requested by non-admin: %d", update.effective_chat.id)
            return
        context.bot.send_message(chat_id=update.effective_chat.id, text="Requesting node DB reset...")
        self.meshtastic_connection.reset_db()

    @check_room
    def traceroute(self, update: Update, context: CallbackContext) -> None:
        """
        Telegram traceroute command

        :param update:
        :param context:
        :return:
        """
        if update.effective_chat.id != self.config.enforce_type(int, self.config.Telegram.Admin):
            self.logger.info("Traceroute requested by non-admin: %d", update.effective_chat.id)
            return
        context.bot.send_message(chat_id=update.effective_chat.id, text="Sending traceroute... See bot logs")
        lora_config = getattr(self.meshtastic_connection.interface.localNode.localConfig, 'lora')
        hop_limit = getattr(lora_config, 'hop_limit')
        dest = update.message.text.lstrip('/traceroute ')
        self.logger.info(f"Sending traceroute request to {dest} (this could take a while)")
        self.bg_route(dest, hop_limit)

    @check_room
    def routes(self, update: Update, _context: CallbackContext) -> None:
        """
        Telegram routes command

        :param update:
        :param _context:
        :return:
        """
        if update.effective_chat.id != self.config.enforce_type(int, self.config.Telegram.Admin):
            self.logger.info("Routes requested by non-admin: %d", update.effective_chat.id)
            return
        lora_config = getattr(self.meshtastic_connection.interface.localNode.localConfig, 'lora')
        hop_limit = getattr(lora_config, 'hop_limit')
        for node in self.meshtastic_connection.nodes_with_position:
            if node_id := node.get('user', {}).get('id'):
                self.bg_route(node_id, hop_limit)

    @check_room
    def qr_code(self, update: Update, context: CallbackContext) -> None:
        """
        qr - Return image containing current channel QR

        :param update:
        :param context:
        :return:
        """
        url = self.meshtastic_connection.interface.localNode.getURL(includeAll=False)
        self.logger.debug(f"Primary channel URL {url}")
        qr_url = pyqrcode.create(url)
        _, tmp = tempfile.mkstemp()
        qr_url.png(tmp, scale=5)
        with open(tmp, 'rb') as photo_handle:
            context.bot.send_photo(chat_id=update.effective_chat.id, photo=photo_handle)
            os.remove(tmp)

    @check_room
    def channel_url(self, update: Update, context: CallbackContext) -> None:
        """
        channel_url - Return current channel URL

        :param update:
        :param context:
        :return:
        """
        url = self.meshtastic_connection.interface.localNode.getURL(includeAll=False)
        self.logger.debug(f"Primary channel URL {url}")
        context.bot.send_message(chat_id=update.effective_chat.id, text=url)

    @check_room
    def uptime(self, update: Update, context: CallbackContext) -> None:
        """
        uptime - Return bot uptime

        :param update:
        :param context:
        :return:
        """
        firmware = 'unknown'
        reboot_count = 'unknown'
        if self.meshtastic_connection.interface.myInfo:
            firmware = self.meshtastic_connection.interface.myInfo.firmware_version
            reboot_count = self.meshtastic_connection.interface.myInfo.reboot_count
        the_version = pkg_resources.get_distribution("meshtastic").version
        formatted_time = humanize.naturaltime(time.time() - self.meshtastic_connection.get_startup_ts)
        text = f'Bot v{VERSION}/FW: v{firmware}/Meshlib: v{the_version}/Reboots: {reboot_count}.'
        text += f'Started {formatted_time}'
        context.bot.send_message(chat_id=update.effective_chat.id, text=text)

    @check_room
    def map_link(self, update: Update, context: CallbackContext) -> None:
        """
        Returns map link to user

        :param update:
        :param context:
        :return:
        """
        msg = 'Map link not enabled'
        map = '''Mapa Principal
http://map.meshtastic.pt

Mapa do Bot
'''
        map2 = '''

Mapa Grafana
http://grafana.meshtastic.pt:3000/
(Username/Password: meshtastic)'''

        if self.config.enforce_type(bool, self.config.Telegram.MapLinkEnabled):
            msg = self.config.enforce_type(str, self.config.Telegram.MapLink)
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text=map+msg+map2)

    @check_room

    def update(self, update: Update, context: CallbackContext) -> None:
            url = 'https://github.com/meshtastic/firmware/releases/latest'
            r = requests.get(url)
            version = r.url.split('/')[-1]
            os.system("""curl --silent https://github.com/meshtastic/firmware/tags | more | grep -A 1 /meshtastic/firmware/releases/tag/v | head -1| grep -o -P '(?<=href="/).*(?=" data-view-component="true" class="Link--primary)' | sed  's/meshtastic\/firmware\/releases\/tag\///g' > /tmp/firmware.vrs""")
            os.system("""curl --silent https://github.com/meshtastic/Meshtastic-Android/tags | more | grep -A 1 /meshtastic/Meshtastic-Android/releases/tag/ | head -1| grep -o -P '(?<=href="/).*(?=" data-view-component="true" class="Link--primary)' | sed  's/meshtastic\/Meshtastic-Android\/releases\/tag\///g' > /tmp/Meshtastic-Android.vrs""")
            #sm1 = os.system('cat /tmp/firmware.vrs')
            p = subprocess.Popen('cat /tmp/firmware.vrs', stdout=subprocess.PIPE, shell=True)
            (output, err) = p.communicate()
            p_status = p.wait()
            sm2 = f'Meshtastic Firmware Beta: ' + version + ''' (Versão Estável)\n'''
            output = output.decode("utf-8")
#https://github.com/meshtastic/firmware/releases/latest


            sm3 = f'Ultima Versão: ' + str(output) + '''https://github.com/meshtastic/firmware/releases

'''
            sms = sm2+sm3

            url = 'https://github.com/meshtastic/Meshtastic-Android/releases/latest'
            r = requests.get(url)
            version = r.url.split('/')[-1]
            sms2A = f'Meshtastic App Android Beta: ' + version + ''' (Versão Estável)\n'''
            p = subprocess.Popen('cat /tmp/Meshtastic-Android.vrs', stdout=subprocess.PIPE, shell=True)
            (output, err) = p.communicate()
            p_status = p.wait()
            output = output.decode("utf-8")
            sm3 = f'Ultima Versão: ' + str(output) + '''https://github.com/meshtastic/Meshtastic-Android/releases

'''
            smsA = sms2A+sm3

            print(str(output))
            print(str(output))
            print(str(output))

#https://github.com/meshtastic/Meshtastic-Android/releases/latest


            url = 'https://github.com/meshtastic/python/releases/latest'
            r = requests.get(url)
            version = r.url.split('/')[-1]
            sms3 = f'Meshtastic Python CLI: ' + version + ''' (Versão Estável)
https://github.com/meshtastic/python/releases

'''

#https://github.com/meshtastic/python/releases/latest


            url = 'https://github.com/meshtastic/c-sharp/releases/latest'
            r = requests.get(url)
            version = r.url.split('/')[-1]
            sms4 = f'Meshtastic CLI Preview: ' + version + ''' (Versão Estável)
https://github.com/meshtastic/c-sharp/releases
'''

#https://github.com/meshtastic/c-sharp/releases/latest
            context.bot.send_message(chat_id=update.effective_chat.id,text=sms+smsA+sms3+sms4)

            self.meshtastic_connection.send_text(sms, destinationId=from_id)
            self.meshtastic_connection.send_text(smsA, destinationId=from_id)
            self.meshtastic_connection.send_text(sms3, destinationId=from_id)
            self.meshtastic_connection.send_text(sms4, destinationId=from_id)


    @check_room


    def nodes(self, update: Update, context: CallbackContext) -> None:
        """
        Returns list of nodes to user

        :param update:
        :param context:
        :return:
        """
        include_self = self.config.enforce_type(bool, self.config.Telegram.NodeIncludeSelf)
        formatted = self.meshtastic_connection.format_nodes(include_self=include_self)

        if len(formatted) < 4096:
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text=formatted,
                                     parse_mode='MarkdownV2')
            return
        split_message(formatted, 4096,
                      lambda msg: context.bot.send_message(chat_id=update.effective_chat.id,
                                                           text=msg,
                                                           parse_mode='MarkdownV2')
                      )

    def bg_route(self, dest, hop_limit):
        """
        Send a traceroute request in the background

        :param dest:
        :param hop_limit:
        :return:
        """
        if len(dest) == 0:
            return
        thread = Thread(target=self.meshtastic_connection.interface.sendTraceRoute,
                        args=(dest, hop_limit), name=f"Traceroute-{dest}")
        thread.start()

    def run(self):
        """
        Telegram bot runner

        :return:
        """
        thread = Thread(target=self.poll, name=self.name)
        thread.start()




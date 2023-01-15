# -*- coding: utf-8 -*-
""" Telegram bot module """

import functools
import logging
import os
import re
import tempfile
import time
#
from threading import Thread
#
import humanize
import pyqrcode
#
from setproctitle import setthreadtitle
from telegram import Update
from telegram.ext import CallbackContext
from telegram.ext import CommandHandler
from telegram.ext import MessageHandler, Filters
#
from mtg.config import Config
from mtg.connection.meshtastic import MeshtasticConnection
from mtg.connection.telegram import TelegramConnection
from mtg.filter import TelegramFilter
from mtg.log import VERSION


def check_room(func):
    """
    check_room - decorator that checks for room permissions
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
        if update.effective_chat.id in rooms and not bot_in_rooms:
            return None
        return func(*args)
    return wrapper


class TelegramBot:
    """
    Telegram bot
    """

    def __init__(self, config: Config, meshtastic_connection: MeshtasticConnection,
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
        maplink_handler = CommandHandler('map', self.map_link)
        resetdb_handler = CommandHandler('reset_db', self.reset_db)
        traceroute_handler = CommandHandler('traceroute', self.traceroute)

        dispatcher = self.telegram_connection.dispatcher

        dispatcher.add_handler(start_handler)
        dispatcher.add_handler(node_handler)
        dispatcher.add_handler(reboot_handler)
        dispatcher.add_handler(qr_handler)
        dispatcher.add_handler(uptime_handler)
        dispatcher.add_handler(maplink_handler)
        dispatcher.add_handler(resetdb_handler)
        dispatcher.add_handler(traceroute_handler)

        echo_handler = MessageHandler(Filters.text & (~Filters.command), self.echo)
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
        full_user = update.effective_user.first_name
        if update.effective_user.last_name is not None:
            full_user += ' ' + update.effective_user.last_name
        self.logger.debug(f"{update.effective_chat.id} {full_user} {update.message.text}")
        self.meshtastic_connection.send_text(f"{full_user}: {update.message.text}")

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
        self.meshtastic_connection.interface.sendTraceRoute(dest, hop_limit)

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
    def uptime(self, update: Update, context: CallbackContext) -> None:
        """
        uptime - Returns bot uptime
        """
        firmware = 'unknown'
        reboot_count = 'unknown'
        if self.meshtastic_connection.interface.myInfo:
            firmware = self.meshtastic_connection.interface.myInfo.firmware_version
            reboot_count = self.meshtastic_connection.interface.myInfo.reboot_count
        formatted_time = humanize.naturaltime(time.time() - self.meshtastic_connection.get_startup_ts)
        text= f'Bot v{VERSION}/FW: v{firmware}/Reboots: {reboot_count}. Started {formatted_time}'
        context.bot.send_message(chat_id=update.effective_chat.id, text=text)

    @check_room
    def map_link(self, update: Update, context: CallbackContext) -> None:
        """
        map_link - Returns map link (if enabled)
        """
        msg = 'Map link not enabled'
        if self.config.enforce_type(bool, self.config.Telegram.MapLinkEnabled):
            msg = self.config.enforce_type(str, self.config.Telegram.MapLink)
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text=msg)

    @staticmethod
    def format_nodes(nodes):
        """
        Formats node list to be more compact

        :param nodes:
        :return:
        """
        nodes = re.sub(r'[╒═╤╕╘╧╛╞╪╡├─┼┤]', '', nodes)
        nodes = nodes.replace('│', ',')
        new_nodes = []
        header = True
        for line in nodes.split('\n'):
            line = line.lstrip(',').rstrip(',').rstrip('\n')
            if not line:
                continue
            # clear column value
            i = 0
            new_line = []
            for column in line.split(','):
                column = column.strip()
                if i == 0:
                    if not header:
                        column = f'**{column}**`'
                    else:
                        column = f'**{column}**'.replace('.', r'\.')
                new_line.append(column + ', ')
                if not header:
                    i += 1
            reassembled_line = ''.join(new_line).rstrip(', ')
            if not header:
                reassembled_line = f'{reassembled_line}`'
            else:
                reassembled_line = f'{reassembled_line}'
            header = False
            new_nodes.append(reassembled_line)
        return '\n'.join(new_nodes)

    @check_room
    def nodes(self, update: Update, context: CallbackContext) -> None:
        """
        Returns list of nodes to user

        :param update:
        :param context:
        :return:
        """
        include_self = self.config.enforce_type(bool, self.config.Telegram.NodeIncludeSelf)
        table = self.meshtastic_connection.interface.showNodes(includeSelf=include_self)
        if not table:
            table = "No other nodes"
        formatted = self.format_nodes(table)
        if len(formatted) <= 4096:
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text=formatted,
                                     parse_mode='MarkdownV2')
        else:
            parts = []
            part = []
            for line in formatted.splitlines('\n'):
                if len('\n'.join(part) + line) < 4096:
                    part.append(line)
                else:
                    parts.append(part)
                    part = [line]
            for part in parts:
                context.bot.send_message(chat_id=update.effective_chat.id,
                                         text='\n'.join(part),
                                         parse_mode='MarkdownV2')


    def run(self):
        """
        Telegram bot runner

        :return:
        """
        thread = Thread(target=self.poll, name=self.name)
        thread.start()

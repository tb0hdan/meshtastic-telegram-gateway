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

        start_handler = CommandHandler('start', self.start)
        node_handler = CommandHandler('nodes', self.nodes)
        reboot_handler = CommandHandler('reboot', self.reboot)
        uptime_handler = CommandHandler('uptime', self.uptime)
        qr_handler = CommandHandler('qr', self.qr_code)
        maplink_handler = CommandHandler('map', self.map_link)
        resetdb_handler = CommandHandler('reset_db', self.reset_db)

        dispatcher = self.telegram_connection.dispatcher

        dispatcher.add_handler(start_handler)
        dispatcher.add_handler(node_handler)
        dispatcher.add_handler(reboot_handler)
        dispatcher.add_handler(qr_handler)
        dispatcher.add_handler(uptime_handler)
        dispatcher.add_handler(maplink_handler)
        dispatcher.add_handler(resetdb_handler)

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

    def qr_code(self, update: Update, context: CallbackContext) -> None:
        """
        qr - Return image containing current channel QR

        :param update:
        :param context:
        :return:
        """
        url = self.meshtastic_connection.interface.localNode.getURL(includeAll=False)
        self.logger.info(f"Primary channel URL {url}")
        qr_url = pyqrcode.create(url)
        _, tmp = tempfile.mkstemp()
        qr_url.png(tmp, scale=5)
        with open(tmp, 'rb') as photo_handle:
            context.bot.send_photo(chat_id=update.effective_chat.id, photo=photo_handle)
            os.remove(tmp)

    def uptime(self, update: Update, context: CallbackContext) -> None:
        """
        uptime - Returns bot uptime
        """
        firmware = 'unknown'
        if self.meshtastic_connection.interface.myInfo:
            firmware = self.meshtastic_connection.interface.myInfo.firmware_version
        formatted_time = humanize.naturaltime(time.time() - self.meshtastic_connection.get_startup_ts)
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text=f'Bot v{VERSION}/FW: {firmware} started {formatted_time}')

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
        for line in nodes.split('\n'):
            line = line.lstrip(',').rstrip(',').rstrip('\n')
            if not line:
                continue
            # clear column value
            new_line = []
            for column in line.split(','):
                column = column.strip()
                new_line.append(column + ', ')
            reassembled_line = ''.join(new_line).rstrip(', ')
            new_nodes.append(f'`{reassembled_line}`')
        return '\n'.join(new_nodes)

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
        thread = Thread(target=self.poll)
        thread.start()

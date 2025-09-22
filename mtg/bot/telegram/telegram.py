# -*- coding: utf-8 -*-
""" Telegram bot module """

import functools
import logging
import os
import re
import tempfile
import time
#
from importlib.metadata import version as importlib_version
from threading import Thread
from typing import Any, Callable, Optional
from urllib.parse import urlparse
#
import humanize
import pyqrcode
import requests
#
from telegram import Update
from telegram.constants import MessageLimit
from telegram.ext import CallbackContext
from telegram.ext import CommandHandler
from telegram.ext import MessageHandler, filters
#
from mtg.config import Config
from mtg.connection.rich import RichConnection
from mtg.connection.telegram import TelegramConnection
from mtg.filter import TelegramFilter
from mtg.log import VERSION
from mtg.utils import split_message


def check_room(func: Callable[..., Any]) -> Callable[..., Any]:
    """
    check_room - decorator to check if bot is in rooms

    :param func:
    :return:
    """

    @functools.wraps(func)
    def wrapper(*args: Any) -> Any:
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
        if bot.filter is not None and bot.filter.banned(str(update.effective_user.id)):
            if bot.logger is not None:
                bot.logger.debug(f"User {update.effective_user.id} is in a blacklist...")
            return None
        return func(*args)

    return wrapper


class TelegramBot:  # pylint:disable=too-many-public-methods
    """
    Telegram bot
    """

    def __init__(self, config: Config, meshtastic_connection: RichConnection,  # pylint:disable=too-many-locals
                 telegram_connection: TelegramConnection):
        self.config = config
        self.filter: Optional[TelegramFilter] = None
        self.logger: logging.Logger = logging.getLogger('Telegram Bot') # default logger
        self.meshtastic_connection = meshtastic_connection
        self.telegram_connection = telegram_connection
        self.aprs = None
        self.name = 'Telegram Bot'

        application = self.telegram_connection.application

        application.add_handler(CommandHandler('start', self.start))
        application.add_handler(CommandHandler('nodes', self.nodes))
        application.add_handler(CommandHandler('reboot', self.reboot))
        application.add_handler(CommandHandler('uptime', self.uptime))
        application.add_handler(CommandHandler('qr', self.qr_code))
        application.add_handler(CommandHandler('ch', self.channel_url))
        application.add_handler(CommandHandler('map', self.map_link))
        application.add_handler(CommandHandler('reset_db', self.reset_db))
        application.add_handler(CommandHandler('traceroute', self.traceroute))
        application.add_handler(CommandHandler('routes', self.routes))
        #
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.echo))


    def set_aprs(self, aprs: Any) -> None:
        """
        Set APRS connection
        """
        self.aprs = aprs

    def set_logger(self, logger: logging.Logger) -> None:
        """
        Set class logger

        :param logger:
        :return:
        """
        self.logger = logger

    def set_filter(self, filter_class: TelegramFilter) -> None:
        """
        Set filter class

        :param filter_class:
        :return:
        """
        self.filter = filter_class

    def shorten_p(self, long_url) -> str:
        """
        Shorten URL using configured service
        """
        if self.config.WebApp.ShortenerService == 'pls':
            return self.shorten_pls(long_url)
        if self.config.WebApp.ShortenerService == 'tly':
            return self.shorten_tly(long_url)
        return long_url

    def shorten_in_text(self, message: str) -> str:
        """
        Shorten URLs in text messages
        """
        splits = message.split(' ')
        replacements = {
            pos: self.shorten_p(part)
            for pos, part in enumerate(splits)
            if re.match('https?://.+', part)
        }
        for pos in replacements:
            replacement = replacements.get(pos)
            if replacement is not None:
                splits[pos] = replacement
        return ' '.join([x for x in splits if x])

    async def echo(self, update: Update, _) -> None:  # pylint:disable=too-many-branches,too-many-statements,too-many-locals
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
        if self.filter is not None and self.filter.banned(str(update.effective_user.id)):
            self.logger.debug("User %s is in a blacklist...", update.effective_user.id)
            return
        # topic support
        if update.message and update.message.is_topic_message and update.message.reply_to_message.forum_topic_created:
            topic = update.message.reply_to_message.forum_topic_created.name
            if topic != 'General':
                self.logger.debug('Topic %s != General', topic)
                return
        # replies
        if update.message and update.message.reply_to_message and update.message.reply_to_message.is_topic_message:
            # Reply not in general
            self.logger.debug('Reply not in General')
            return
        #
        full_user = update.effective_user.first_name
        if update.effective_user.last_name is not None:
            full_user += f' {update.effective_user.last_name}'
        message = ''
        if update.message and update.message.text:
            message += self.shorten_in_text(update.message.text)

        if update.message and update.message.sticker:
            message += f"sent sticker {update.message.sticker.set_name}: {update.message.sticker.emoji}"

        if update.message and update.message.photo:
            photo = sorted(update.message.photo, key=lambda x: x.file_size, reverse=True)[0]
            photo_file = photo.get_file()
            original_filename = os.path.basename(urlparse(photo_file.file_path).path)
            # Sanitize filename to prevent path traversal
            safe_filename = ''.join(c for c in original_filename if c.isalnum() or c in '._-')
            if not safe_filename:
                safe_filename = f'image_{int(time.time())}.jpg'
            time_stamp = time.strftime('%Y/%m/%d')
            photo_dir = f'./web/static/t/{time_stamp}'
            os.makedirs(photo_dir, exist_ok=True)
            # Ensure the final path is within the expected directory
            final_path = os.path.abspath(f'{photo_dir}/{safe_filename}')
            expected_dir = os.path.abspath(photo_dir)
            if not final_path.startswith(expected_dir):
                safe_filename = f'image_{int(time.time())}.jpg'
                final_path = os.path.abspath(f'{photo_dir}/{safe_filename}')
            photo_file.download(final_path)
            long_url = f'{self.config.WebApp.ExternalURL}/static/t/{time_stamp}/{safe_filename}'
            short_url = self.shorten_p(long_url)
            message += f"sent image: {short_url}"
            self.logger.info(message)

        # check if we got our message
        if not message:
            return
        self.logger.debug("%s %s %s", update.effective_chat.id, full_user, message)
        if message.startswith('APRS-'):
            addressee = message.split(' ', maxsplit=1)[0].lstrip('APRS-').rstrip(':')
            msg = message.replace(message.split(' ', maxsplit=1)[0], '').strip()
            if self.aprs is not None:
                self.aprs.send_text(addressee, f'{full_user}: {msg}')
        self.meshtastic_connection.send_text(f"{full_user}: {message}")

    def shorten_tly(self, long_url: str) -> str:
        """
        Shorten URL using t.ly
        """
        try:
            tly_token = self.config.WebApp.TLYToken
            url = 'https://t.ly/api/v1/link/shorten'
            headers = {
                  'Authorization': f"Bearer {tly_token}",
                  'Content-Type': 'application/json',
                  'Accept': 'application/json'
            }
            response = requests.request('POST', url, headers=headers, json={'long_url': long_url}, timeout=10)
            response.raise_for_status()
            result = response.json()
            return result.get('short_url', long_url)
        except (requests.RequestException, ValueError, KeyError) as exc:
            self.logger.error("URL shortening failed: %s", exc)
            return long_url

    def shorten_pls(self, long_url: str) -> str:
        """
        Shorten URL using pls.st
        """
        try:
            token = self.config.WebApp.PLSST
            url = 'https://pls.st/api/v1/a/links/shorten'
            headers = {
                  'Authorization': f"Bearer {token}",
                  'Content-Type': 'application/json',
                  'Accept': 'application/json'
            }
            response = requests.request('POST', url, headers=headers, json={'url': long_url}, timeout=10)
            response.raise_for_status()
            result = response.json()
            return result.get('short_url', long_url)
        except (requests.RequestException, ValueError, KeyError) as exc:
            self.logger.error("URL shortening failed: %s", exc)
            return long_url


    def poll(self) -> None:
        """
        Telegram bot poller. Uses connection under the hood

        :return:
        """
        self.telegram_connection.poll()

    @check_room
    async def start(self, update: Update, _context: CallbackContext) -> None:
        """
        Telegram /start command handler.

        :param update:
        :param _context:
        :return:
        """
        chat_id = update.effective_chat.id
        self.logger.info("Got /start from %s", chat_id)
        bot = update.get_bot()
        await bot.send_message(chat_id=chat_id, text="I'm a bot, please talk to me!")

    @check_room
    async def reboot(self, update: Update, _context: CallbackContext) -> None:
        """
        Telegram reboot command

        :param update:
        :param _context:
        :return:
        """
        # SECURITY WARNING: Authentication based only on chat ID is weak and can be spoofed
        # Consider implementing proper token-based or username+password authentication
        if update.effective_chat.id != self.config.enforce_type(int, self.config.Telegram.Admin):
            self.logger.warning("Reboot requested by non-admin: %d", update.effective_chat.id)
            return
        bot = update.get_bot()
        await bot.send_message(chat_id=update.effective_chat.id, text="Requesting reboot...")
        self.meshtastic_connection.reboot()

    @check_room
    async def reset_db(self, update: Update, _context: CallbackContext) -> None:
        """
        Telegram reset node DB command

        :param update:
        :param _context:
        :return:
        """
        if update.effective_chat.id != self.config.enforce_type(int, self.config.Telegram.Admin):
            self.logger.info("Reset node DB requested by non-admin: %d", update.effective_chat.id)
            return
        bot = update.get_bot()
        await bot.send_message(chat_id=update.effective_chat.id, text="Requesting node DB reset...")
        self.meshtastic_connection.reset_db()

    @check_room
    async def traceroute(self, update: Update, _context: CallbackContext) -> None:
        """
        Telegram traceroute command

        :param update:
        :param _context:
        :return:
        """
        if update.effective_chat.id != self.config.enforce_type(int, self.config.Telegram.Admin):
            self.logger.info("Traceroute requested by non-admin: %d", update.effective_chat.id)
            return
        bot = update.get_bot()
        await bot.send_message(chat_id=update.effective_chat.id, text="Sending traceroute... See bot logs")
        if self.meshtastic_connection.interface is not None:
            lora_config = getattr(self.meshtastic_connection.interface.localNode.localConfig, 'lora')
        else:
            return
        hop_limit = getattr(lora_config, 'hop_limit')
        dest = update.message.text.lstrip('/traceroute ')
        self.logger.info("Sending traceroute request to %s this could take a while)", dest)
        self.bg_route(dest, hop_limit)

    @check_room
    async def routes(self, update: Update, _context: CallbackContext) -> None:
        """
        Telegram routes command

        :param update:
        :param _context:
        :return:
        """
        if update.effective_chat.id != self.config.enforce_type(int, self.config.Telegram.Admin):
            self.logger.info("Routes requested by non-admin: %d", update.effective_chat.id)
            return
        if self.meshtastic_connection.interface is not None:
            lora_config = getattr(self.meshtastic_connection.interface.localNode.localConfig, 'lora')
        else:
            return
        hop_limit = getattr(lora_config, 'hop_limit')
        for node in self.meshtastic_connection.nodes_with_position:
            if node_id := node.get('user', {}).get('id'):
                self.bg_route(node_id, hop_limit)

    @check_room
    async def qr_code(self, update: Update, _context: CallbackContext) -> None:
        """
        qr - Return image containing current channel QR

        :param update:
        :param _context:
        :return:
        """
        if self.meshtastic_connection.interface is not None:
            url = self.meshtastic_connection.interface.localNode.getURL(includeAll=False)
        else:
            return
        self.logger.debug("Primary channel URL %s", url)
        qr_url = pyqrcode.create(url)
        _, tmp = tempfile.mkstemp()
        qr_url.png(tmp, scale=5)
        bot = update.get_bot()
        with open(tmp, 'rb') as photo_handle:
            await bot.send_photo(chat_id=update.effective_chat.id, photo=photo_handle)
            os.remove(tmp)

    @check_room
    async def channel_url(self, update: Update, _context: CallbackContext) -> None:
        """
        channel_url - Return current channel URL

        :param update:
        :param _context:
        :return:
        """
        if self.meshtastic_connection.interface is not None:
            url = self.meshtastic_connection.interface.localNode.getURL(includeAll=False)
        else:
            return
        self.logger.debug("Primary channel URL %s", url)
        bot = update.get_bot()
        await bot.send_message(chat_id=update.effective_chat.id, text=url)

    @check_room
    async def uptime(self, update: Update, _context: CallbackContext) -> None:
        """
        uptime - Return bot uptime

        :param update:
        :param _context:
        :return:
        """
        firmware = 'unknown'
        reboot_count = 'unknown'
        if (self.meshtastic_connection.interface is not None and
            self.meshtastic_connection.interface.myInfo is not None and
            self.meshtastic_connection.interface.metadata is not None):
            firmware = self.meshtastic_connection.interface.metadata.firmware_version
            reboot_count = str(self.meshtastic_connection.interface.myInfo.reboot_count)
        the_version = importlib_version('meshtastic')
        formatted_time = humanize.naturaltime(time.time() - self.meshtastic_connection.get_startup_ts)
        text = f'Bot v{VERSION}/FW: v{firmware}/Meshlib: v{the_version}/Reboots: {reboot_count}.'
        text += f'Started {formatted_time}'
        bot = update.get_bot()
        await bot.send_message(chat_id=update.effective_chat.id, text=text)

    @check_room
    async def map_link(self, update: Update, _context: CallbackContext) -> None:
        """
        Returns map link to user

        :param update:
        :param _context:
        :return:
        """
        msg = 'Map link not enabled'
        if self.config.enforce_type(bool, self.config.Telegram.MapLinkEnabled):
            msg = str(self.config.enforce_type(str, self.config.Telegram.MapLink))
        bot = update.get_bot()
        await bot.send_message(chat_id=update.effective_chat.id,
                                 text=msg)

    @check_room
    async def nodes(self, update: Update, _context: CallbackContext) -> None:
        """
        Returns list of nodes to user

        :param update:
        :param _context:
        :return:
        """
        include_self = self.config.enforce_type(bool, self.config.Telegram.NodeIncludeSelf)
        formatted = self.meshtastic_connection.format_nodes(include_self=include_self)

        bot = update.get_bot()
        if len(formatted) < MessageLimit.MAX_TEXT_LENGTH:
            await bot.send_message(chat_id=update.effective_chat.id,
                                     text=formatted,
                                     parse_mode='MarkdownV2')
            return
        split_message(formatted, MessageLimit.MAX_TEXT_LENGTH,  # type: ignore[func-returns-value]
                      lambda msg: self.telegram_connection.send_message(chat_id=update.effective_chat.id,
                                                           text=msg,
                                                           parse_mode='MarkdownV2')
                      )

    def bg_route(self, dest: str, hop_limit: int) -> None:
        """
        Send a traceroute request in the background

        :param dest:
        :param hop_limit:
        :return:
        """
        if not dest:
            return
        if self.meshtastic_connection.interface is not None:
            thread = Thread(target=self.meshtastic_connection.interface.sendTraceRoute,
                            args=(dest, hop_limit), name=f"Traceroute-{dest}")
            thread.start()

    def shutdown(self) -> None:
        """
        Telegram bot shutdown method
        """
        self.telegram_connection.shutdown()

    def run(self) -> None:
        """
        Telegram bot runner

        :return:
        """
        self.poll()

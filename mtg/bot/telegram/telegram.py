# -*- coding: utf-8 -*-
""" Telegram bot module """

import functools
import logging
import json
import os
import pkg_resources
import re
import tempfile
import time
from datetime import timedelta
from typing import Optional, Tuple
#
from threading import Thread
from urllib.parse import urlparse
#
import humanize
import pyqrcode
import requests
# pylint:disable=no-name-in-module
from setproctitle import setthreadtitle
from telegram import Update
from telegram.constants import MAX_MESSAGE_LENGTH
from telegram.ext import CallbackContext
from telegram.ext import CommandHandler
from telegram.ext import MessageHandler, Filters
#
from mtg.config import Config
from mtg.connection.rich import RichConnection
from mtg.connection.telegram import MessageReactionHandler, TelegramConnection
from mtg.database import (
    MESSAGE_DIRECTION_MESH_TO_TELEGRAM,
    MESSAGE_DIRECTION_TELEGRAM_TO_MESH,
)
from mtg.filter import TelegramFilter
from mtg.log import VERSION
from mtg.utils import split_message, is_emoji_reaction, first_emoji_codepoint


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
        rooms = [
            room_id
            for room_id in (bot._notifications_room_id, bot._room_id)
            if room_id is not None
        ]
        bot_in_rooms = bot._bot_in_rooms
        # check rooms
        if update.effective_chat and update.effective_chat.id in rooms and not bot_in_rooms:
            return None
        # check blacklist as well
        if bot.filter and update.effective_user and bot.filter.banned(str(update.effective_user.id)):
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
        self.filter = None
        self.logger = None
        self.meshtastic_connection = meshtastic_connection
        self.telegram_connection = telegram_connection
        self.aprs = None
        self.name = 'Telegram Bot'
        self._room_id: Optional[int] = None
        self._notifications_room_id: Optional[int] = None
        self._admin_id: Optional[int] = None
        self._bot_in_rooms: bool = False


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


        log_handler = MessageHandler(Filters.all, self.log_update)
        dispatcher.add_handler(log_handler, group=0)

        reaction_handler = MessageReactionHandler(self.handle_reaction)
        dispatcher.add_handler(reaction_handler, group=1)

        echo_handler = MessageHandler(~Filters.command, self.echo)
        dispatcher.add_handler(echo_handler, group=1)

        self._refresh_cached_config()


    def set_aprs(self, aprs):
        """
        Set APRS connection
        """
        self.aprs = aprs

    def set_logger(self, logger: logging.Logger):
        """
        Set class logger

        :param logger:
        :return:
        """
        self.logger = logger
        self._refresh_cached_config()
        self._deliver_pending_messages()

    def set_filter(self, filter_class: TelegramFilter):
        """
        Set filter class

        :param filter_class:
        :return:
        """
        self.filter = filter_class

    def _deliver_pending_messages(self) -> None:
        """Attempt to resend any pending Telegram-to-Meshtastic messages."""

        if not hasattr(self.meshtastic_connection, 'database'):
            return
        database = self.meshtastic_connection.database
        try:
            pending = list(database.iter_pending_links(MESSAGE_DIRECTION_TELEGRAM_TO_MESH))
        except Exception as exc:  # pylint:disable=broad-except
            if self.logger:
                self.logger.error(
                    'Failed to load pending Telegram messages: %s',
                    repr(exc),
                    exc_info=True,
                )
            return

        for record in pending:
            try:
                self._resend_pending_record(record)
            except Exception as exc:  # pylint:disable=broad-except
                if self.logger:
                    self.logger.error(
                        'Pending Telegram message %s failed: %s',
                        record.id,
                        repr(exc),
                        exc_info=True,
                    )
                database.mark_link_retry(record.id, repr(exc))

    def _resend_pending_record(self, record) -> None:
        """Resend a single pending message record."""

        database = self.meshtastic_connection.database
        sanitized_reply_id = self._coerce_optional_int(
            record.reply_to_packet_id,
            context='pending reply_to_packet_id',
        )
        sanitized_emoji = self._coerce_optional_int(record.emoji, context='pending emoji code')
        if record.reply_to_packet_id is not None and sanitized_reply_id is None:
            database.mark_link_failed(record.id, 'invalid reply_to_packet_id value')
            return
        if record.emoji is not None and sanitized_emoji is None:
            database.mark_link_failed(record.id, 'invalid emoji value')
            return
        if sanitized_emoji is not None:
            if sanitized_reply_id is None:
                database.mark_link_failed(record.id, 'missing reply target for emoji reaction')
                return
            packets = self.meshtastic_connection.send_text(
                '',
                reply_id=sanitized_reply_id,
                emoji=sanitized_emoji,
            )
        else:
            sender = record.sender or 'Telegram'
            payload = record.payload or ''
            packets = self.meshtastic_connection.send_user_text(
                sender,
                payload,
                reply_id=sanitized_reply_id,
            )
        if not packets:
            database.mark_link_retry(record.id, 'meshtastic send returned None')
            return
        first_packet = packets[0]
        database.mark_link_sent(record.id, meshtastic_packet_id=first_packet.id)
        previous_packet_id = sanitized_reply_id
        for packet in packets:
            database.add_link_alias(
                record.id,
                packet.id,
                previous_packet_id=previous_packet_id,
            )
            previous_packet_id = packet.id

    @staticmethod
    def _split_sender_payload(text: str) -> Tuple[Optional[str], str]:
        """Return sender/payload extracted from a Telegram message body."""

        if not text:
            return None, ''
        candidate = text.strip()
        sender: Optional[str] = None
        payload = candidate
        prefix, separator, suffix = candidate.partition(': ')
        if separator and prefix and suffix:
            sender = prefix.strip()
            payload = suffix.strip()
        return sender, payload

    @staticmethod
    def _format_reply_hint(message) -> Optional[str]:  # pragma: no cover - simple formatting
        """Produce a compact hint describing the replied-to Telegram message."""

        text = getattr(message, 'text', None) or getattr(message, 'caption', None)
        if not text:
            return None
        compact = ' '.join(text.strip().split())
        if len(compact) > 60:
            return f"{compact[:57]}…"
        return compact

    def _attempt_reply_backfill(self, update: Update) -> Optional[object]:
        """Reconstruct missing Telegram→Meshtastic mapping when possible."""

        if not hasattr(self.meshtastic_connection, 'database'):
            return None
        reply_to = getattr(update.message, 'reply_to_message', None)
        if not reply_to:
            return None
        text = getattr(reply_to, 'text', None) or getattr(reply_to, 'caption', None)
        if not text:
            return None
        sender, payload = self._split_sender_payload(text)
        database = self.meshtastic_connection.database
        record = database.find_recent_link_by_payload(
            MESSAGE_DIRECTION_MESH_TO_TELEGRAM,
            payload,
            sender=sender,
            max_age=timedelta(hours=12),
        )
        if record is None and sender is not None:
            record = database.find_recent_link_by_payload(
                MESSAGE_DIRECTION_MESH_TO_TELEGRAM,
                payload,
                max_age=timedelta(hours=12),
            )
        if record is None or record.meshtastic_packet_id is None:
            return None
        thread_id = getattr(reply_to, 'message_thread_id', None)
        database.attach_telegram_metadata(
            record.id,
            telegram_chat_id=update.effective_chat.id,
            telegram_message_id=reply_to.message_id,
            telegram_thread_id=thread_id,
        )
        if self.logger:
            self.logger.warning(
                'Recovered missing reply mapping for Telegram message %s via payload match',
                reply_to.message_id,
            )
        return database.get_link_by_telegram(update.effective_chat.id, reply_to.message_id)

    def log_update(self, update: Update, _context: CallbackContext) -> None:
        """Log every incoming Telegram update"""
        msg = update.effective_message
        data = {
            "event": "telegram_update",
            "chat_id": update.effective_chat.id if update.effective_chat else None,
            "user_id": update.effective_user.id if update.effective_user else None,
            "message_id": msg.message_id if msg else None,
        }
        self.logger.info(json.dumps(data))

    def shorten_p(self, long_url) -> str:
        """
        Shorten URL using configured service
        """
        if self.config.WebApp.ShortenerService == 'pls':
            short_url = self.shorten_pls(long_url)
        elif self.config.WebApp.ShortenerService == 'tly':
            short_url = self.shorten_tly(long_url)
        else:
            short_url = long_url
        if not short_url:
            short_url = long_url
        return short_url

    def shorten_in_text(self, message) -> str:
        """Shorten URLs in text messages"""
        splits = message.split(' ')
        replacements = {}
        for pos, part in enumerate(splits):
            if re.match('https?://.+', part):
                replacements[pos] = self.shorten_p(part)
        for pos in replacements:
            splits[pos] = replacements.get(pos)
        return ' '.join([x for x in splits if x])

    def _handle_photo(self, message: str, update: Update) -> str:
        """Save photo attachment and return updated message"""
        photo = sorted(update.message.photo, key=lambda x: x.file_size, reverse=True)[0]
        photo_file = photo.get_file()
        file_path = os.path.basename(urlparse(photo_file.file_path).path)
        time_stamp = time.strftime('%Y/%m/%d')
        photo_dir = f'./web/static/t/{time_stamp}'
        os.makedirs(photo_dir, exist_ok=True)
        photo_file.download(f'{photo_dir}/{file_path}')
        external_url = getattr(self.config.WebApp, 'ExternalURL', '')
        # Skip generating URL if configuration still uses placeholder domain
        if external_url and 'example.com' not in external_url:
            long_url = f"{external_url.rstrip('/')}/static/t/{time_stamp}/{file_path}"
            short_url = self.shorten_p(long_url)
            if message:
                message += ' '
            message += f"sent image: {short_url}"
        else:
            if message:
                message += ' '
            message += 'sent image'
        self.logger.info(message)
        return message

    def echo(self, update: Update, _) -> None:  # pylint:disable=too-many-branches
        """
        Telegram bot echo handler. Does actual message forwarding

        :param update:
        :param _:
        :return:
        """
        room_id = self._room_id
        if room_id is None:
            self._get_logger().error('Telegram.Room is not configured with a valid integer value')
            return
        if update.effective_chat.id != room_id:
            self.logger.warning(
                "Ignoring message from chat %d; configured chat is %d",
                update.effective_chat.id,
                room_id,
            )
            return
        if self.filter and self.filter.banned(str(update.effective_user.id)):
            self.logger.debug(f"User {update.effective_user.id} is in a blacklist...")
            return
        # topic support
        if update.message and update.message.is_topic_message:
            forum_topic = None
            if update.message.reply_to_message:
                forum_topic = getattr(update.message.reply_to_message, 'forum_topic_created', None)
            if forum_topic and forum_topic.name != 'General':
                self.logger.debug(f'Topic {forum_topic.name} != General')
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
        if update.message and update.message.caption:
            if message:
                message += ' '
            message += self.shorten_in_text(update.message.caption)

        if update.message and update.message.sticker:
            message += f"sent sticker {update.message.sticker.set_name}: {update.message.sticker.emoji}"

        if update.message and update.message.photo:
            message = self._handle_photo(message, update)

        # check if we got our message
        if not message:
            return
        self.logger.debug(f"{update.effective_chat.id} {full_user} {message}")

        reply_packet_id = None
        reply_hint = None
        if update.message and update.message.reply_to_message:
            reply_record = self.meshtastic_connection.database.get_link_by_telegram(
                update.effective_chat.id,
                update.message.reply_to_message.message_id,
            )
            if reply_record is None:
                try:
                    reply_record = self._attempt_reply_backfill(update)
                except Exception as exc:  # pylint:disable=broad-except
                    self._get_logger().warning(
                        'Failed to backfill reply mapping for Telegram message %s: %s',
                        update.message.reply_to_message.message_id,
                        repr(exc),
                        exc_info=True,
                    )
            if reply_record is None:
                self.logger.debug(
                    'No Meshtastic mapping found for Telegram reply %s in chat %s',
                    update.message.reply_to_message.message_id,
                    update.effective_chat.id,
                )
            elif reply_record.meshtastic_packet_id is None:
                self.logger.debug(
                    'Telegram reply %s is linked without a Meshtastic packet id',
                    update.message.reply_to_message.message_id,
                )
            else:
                reply_packet_id = self._coerce_optional_int(
                    reply_record.meshtastic_packet_id,
                    context='reply mapping packet id',
                )
                if reply_packet_id is None:
                    self._get_logger().warning(
                        'Ignoring invalid reply mapping for Telegram message %s: %r',
                        update.message.reply_to_message.message_id,
                        reply_record.meshtastic_packet_id,
                    )
                else:
                    self.logger.debug(
                        'Forwarding Telegram message %s as reply to Meshtastic packet %s',
                        update.message.message_id if update.message else None,
                        reply_packet_id,
                    )
            if reply_packet_id is None:
                reply_hint = self._format_reply_hint(update.message.reply_to_message)
        if reply_packet_id is None and update.message and update.message.reply_to_message:
            self.logger.debug(
                'Unable to resolve Meshtastic reply target for Telegram message %s -> replied to %s',
                update.message.message_id,
                update.message.reply_to_message.message_id,
            )
            if reply_hint:
                message += f" (reply to: {reply_hint})"
                self.logger.debug(
                    'Added reply context hint for Telegram message %s: %s',
                    update.message.message_id,
                    reply_hint,
                )

        text_content = update.message.text if update.message else ''
        if update.message and update.message.text and is_emoji_reaction(text_content):
            if reply_packet_id is None:
                self.logger.debug('Ignoring emoji reaction without mapped Meshtastic message')
                return
            emoji_code = first_emoji_codepoint(text_content)
            if emoji_code is None:
                return
            record = self.meshtastic_connection.database.ensure_message_link(
                direction=MESSAGE_DIRECTION_TELEGRAM_TO_MESH,
                telegram_chat_id=update.effective_chat.id,
                telegram_message_id=update.message.message_id,
                payload='',
                sender=full_user,
                reply_to_packet_id=reply_packet_id,
                emoji=emoji_code,
            )
            log_data = {
                "event": "telegram_to_mesh_reaction",
                "user": full_user,
                "emoji": emoji_code,
                "message_id": update.message.message_id,
                "reply_packet_id": reply_packet_id,
            }
            self.logger.info(json.dumps(log_data))
            packets = self.meshtastic_connection.send_text(
                '',
                reply_id=reply_packet_id,
                emoji=emoji_code,
            )
            if packets:
                self.meshtastic_connection.database.mark_link_sent(
                    record.id,
                    meshtastic_packet_id=packets[0].id,
                )
            else:
                self.meshtastic_connection.database.mark_link_retry(
                    record.id,
                    'meshtastic send returned None',
                )
            return

        if message.startswith('APRS-'):
            addressee = message.split(' ', maxsplit=1)[0].lstrip('APRS-').rstrip(':')
            msg = message.replace(message.split(' ', maxsplit=1)[0], '').strip()
            self.aprs.send_text(addressee, f'{full_user}: {msg}')
        log_data = {
            "event": "telegram_to_mesh",
            "user": full_user,
            "message": message,
            "message_id": update.message.message_id if update.message else None,
            "reply_packet_id": reply_packet_id,
        }
        self.logger.info(json.dumps(log_data))
        record = self.meshtastic_connection.database.ensure_message_link(
            direction=MESSAGE_DIRECTION_TELEGRAM_TO_MESH,
            telegram_chat_id=update.effective_chat.id,
            telegram_message_id=update.message.message_id if update.message else None,
            payload=message,
            sender=full_user,
            reply_to_packet_id=reply_packet_id,
        )
        packets = self.meshtastic_connection.send_user_text(full_user, message, reply_id=reply_packet_id)
        if not packets:
            self.meshtastic_connection.database.mark_link_retry(
                record.id,
                'meshtastic send returned None',
            )
            return

        first_packet = packets[0]
        self.meshtastic_connection.database.mark_link_sent(
            record.id,
            meshtastic_packet_id=first_packet.id,
        )
        previous_packet_id = reply_packet_id
        for packet in packets:
            self.meshtastic_connection.database.add_link_alias(
                record.id,
                packet.id,
                previous_packet_id=previous_packet_id,
            )
            previous_packet_id = packet.id

    def handle_reaction(self, update: Update, _context: CallbackContext) -> None:  # pylint:disable=too-many-branches
        """Forward Telegram emoji reactions to Meshtastic."""

        reaction = getattr(update, 'message_reaction', None)
        if reaction is None:
            return

        room_id = self._room_id
        if room_id is None:
            self._get_logger().error('Telegram.Room is not configured with a valid integer value')
            return

        chat = reaction.chat or update.effective_chat
        if chat is None:
            self.logger.debug('Ignoring reaction without chat context')
            return
        if chat.id != room_id:
            self.logger.debug(
                'Ignoring reaction from chat %s; configured chat is %s',
                chat.id,
                room_id,
            )
            return

        user = update.effective_user
        if self.filter and user and self.filter.banned(str(user.id)):
            self.logger.debug(f"User {user.id} is in a blacklist...")
            return

        bot_user_id = getattr(self.telegram_connection.updater.bot, 'id', None)
        if user and getattr(user, 'is_bot', False):
            if bot_user_id == user.id:
                self.logger.debug('Ignoring reaction generated by the bridge bot user %s', user.id)
                return
            self.logger.debug('Ignoring reaction from bot user %s', user.id)
            return

        actor_chat = getattr(reaction, 'actor_chat', None)
        if user is None and actor_chat is not None and bot_user_id is not None and actor_chat.id == bot_user_id:
            self.logger.debug('Ignoring reaction generated by the bridge bot actor chat %s', actor_chat.id)
            return

        emoji_entry = None
        for candidate in getattr(reaction, 'new_reaction', []) or []:
            if getattr(candidate, 'type', None) == 'emoji' and getattr(candidate, 'emoji', None):
                emoji_entry = candidate
                break
        if emoji_entry is None:
            self.logger.debug('Ignoring reaction update without a supported emoji payload')
            return

        emoji_code = first_emoji_codepoint(emoji_entry.emoji)
        if emoji_code is None:
            self.logger.debug('Ignoring reaction with unsupported emoji: %r', emoji_entry.emoji)
            return

        record = self.meshtastic_connection.database.get_link_by_telegram(chat.id, reaction.message_id)
        if record is None:
            self.logger.debug(
                'Ignoring reaction for Telegram message %s without stored Meshtastic mapping',
                reaction.message_id,
            )
            return
        if record.meshtastic_packet_id is None:
            self.logger.debug(
                'Ignoring reaction for Telegram message %s missing Meshtastic packet id',
                reaction.message_id,
            )
            return

        reply_packet_id = self._coerce_optional_int(
            record.meshtastic_packet_id,
            context='reaction mapping packet id',
        )
        if reply_packet_id is None:
            self.logger.debug(
                'Ignoring reaction with invalid Meshtastic packet id %r',
                record.meshtastic_packet_id,
            )
            return

        full_user = ''
        if user:
            full_user = user.first_name or ''
            if user.last_name:
                full_user = f"{full_user} {user.last_name}".strip()
            if not full_user and getattr(user, 'username', None):
                full_user = user.username
        elif actor_chat is not None:
            full_user = (
                getattr(actor_chat, 'title', None)
                or getattr(actor_chat, 'username', None)
                or str(actor_chat.id)
            )
        if not full_user:
            full_user = 'Telegram'

        link_record = self.meshtastic_connection.database.ensure_message_link(
            direction=MESSAGE_DIRECTION_TELEGRAM_TO_MESH,
            telegram_chat_id=chat.id,
            payload='',
            sender=full_user,
            reply_to_packet_id=reply_packet_id,
            emoji=emoji_code,
        )

        log_data = {
            "event": "telegram_to_mesh_reaction",
            "user": full_user,
            "emoji": emoji_code,
            "message_id": reaction.message_id,
            "reply_packet_id": reply_packet_id,
        }
        self.logger.info(json.dumps(log_data))

        packets = self.meshtastic_connection.send_text(
            '',
            reply_id=reply_packet_id,
            emoji=emoji_code,
        )
        if packets:
            self.meshtastic_connection.database.mark_link_sent(
                link_record.id,
                meshtastic_packet_id=packets[0].id,
            )
        else:
            self.meshtastic_connection.database.mark_link_retry(
                link_record.id,
                'meshtastic send returned None',
            )

    def shorten_tly(self, long_url):
        """
        Shorten URL using t.ly
        """
        tly_token = self.config.WebApp.TLYToken
        url = 'https://t.ly/api/v1/link/shorten'
        headers = {
              'Authorization': f"Bearer {tly_token}",
              'Content-Type': 'application/json',
              'Accept': 'application/json'
        }
        response = requests.request('POST', url, headers=headers, json={'long_url': long_url}, timeout=10)
        return response.json().get('short_url')

    def shorten_pls(self, long_url):
        """
        Shorten URL using pls.st
        """
        token = self.config.WebApp.PLSST
        url = 'https://pls.st/api/v1/a/links/shorten'
        headers = {
              'Authorization': f"Bearer {token}",
              'Content-Type': 'application/json',
              'Accept': 'application/json'
        }
        response = requests.request('POST', url, headers=headers, json={'url': long_url}, timeout=10)
        return response.json().get('short_url')


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
        if self._admin_id is None:
            self._get_logger().error('Telegram.Admin is not configured with a valid integer value')
            return
        if update.effective_chat.id != self._admin_id:
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
        if self._admin_id is None:
            self._get_logger().error('Telegram.Admin is not configured with a valid integer value')
            return
        if update.effective_chat.id != self._admin_id:
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
        if self._admin_id is None:
            self._get_logger().error('Telegram.Admin is not configured with a valid integer value')
            return
        if update.effective_chat.id != self._admin_id:
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
        if self._admin_id is None:
            self._get_logger().error('Telegram.Admin is not configured with a valid integer value')
            return
        if update.effective_chat.id != self._admin_id:
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
        if self.meshtastic_connection.interface.myInfo and self.meshtastic_connection.interface.metadata:
            firmware = self.meshtastic_connection.interface.metadata.firmware_version
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
        if self._get_telegram_bool('MapLinkEnabled', default=False):
            msg = self.config.enforce_type(str, self.config.Telegram.MapLink)
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text=msg)

    @check_room
    def nodes(self, update: Update, context: CallbackContext) -> None:
        """
        Returns list of nodes to user

        :param update:
        :param context:
        :return:
        """
        include_self = self._get_telegram_bool('NodeIncludeSelf', default=False)
        formatted = self.meshtastic_connection.format_nodes(include_self=include_self)

        if len(formatted) < MAX_MESSAGE_LENGTH:
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text=formatted,
                                     parse_mode='MarkdownV2')
            return
        split_message(formatted, MAX_MESSAGE_LENGTH,
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

    def shutdown(self):
        """
        Telegram bot shutdown method
        """
        self.telegram_connection.shutdown()

    def run(self):
        """
        Telegram bot runner

        :return:
        """
        thread = Thread(target=self.poll, name=self.name)
        thread.start()

    def _get_logger(self) -> logging.Logger:
        """Return the configured logger or fall back to the module logger."""

        return self.logger or logging.getLogger(__name__)

    def _refresh_cached_config(self) -> None:
        """Cache frequently used Telegram configuration values with validation."""

        self._room_id = self._get_telegram_int('Room')
        self._notifications_room_id = self._get_telegram_int('NotificationsRoom')
        self._admin_id = self._get_telegram_int('Admin')
        self._bot_in_rooms = self._get_telegram_bool('BotInRooms', default=False)

    def _get_telegram_int(self, key: str, default: Optional[int] = None) -> Optional[int]:
        """Safely read an integer value from the Telegram configuration section."""

        logger = self._get_logger()
        try:
            raw_value = getattr(self.config.Telegram, key)
        except (AttributeError, KeyError):
            logger.error('Telegram.%s is missing from configuration', key)
            return default
        try:
            return self.config.enforce_type(int, raw_value)
        except (TypeError, ValueError) as exc:
            logger.error('Invalid Telegram.%s value %r: %s', key, raw_value, exc)
            return default

    def _get_telegram_bool(self, key: str, default: bool = False) -> bool:
        """Safely read a boolean value from the Telegram configuration section."""

        logger = self._get_logger()
        try:
            raw_value = getattr(self.config.Telegram, key)
        except (AttributeError, KeyError):
            logger.error('Telegram.%s is missing from configuration', key)
            return default
        if isinstance(raw_value, bool):
            return raw_value
        try:
            return self.config.enforce_type(bool, raw_value)
        except (AttributeError, TypeError, ValueError) as exc:
            logger.error('Invalid Telegram.%s value %r: %s', key, raw_value, exc)
            return default

    def _coerce_optional_int(self, value: Optional[object], *, context: str) -> Optional[int]:
        """Best-effort conversion of optional values to integers."""

        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            self._get_logger().warning('Invalid %s %r: %s', context, value, exc)
            return None

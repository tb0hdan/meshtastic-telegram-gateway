# -*- coding: utf-8 -*-
""" Telegram connection module """


import logging
import time

import telegram
from pkg_resources import parse_version
from telegram.error import NetworkError, TelegramError
from telegram.ext import Updater
# pylint:disable=no-name-in-module
from setproctitle import setthreadtitle


from .reaction import ensure_reaction_update_support


class TelegramConnection:
    """
    Telegram connection
    """

    def __init__(self, token: str, logger: logging.Logger):
        self.logger = logger
        self.token = token
        if parse_version(telegram.__version__) < parse_version("13.15"):
            raise RuntimeError(
                f"Unsupported python-telegram-bot version {telegram.__version__}; "
                "please install 13.15"
            )
        ensure_reaction_update_support()
        self.updater = Updater(token=token, use_context=True)
        self.exit = False
        self.name = 'Telegram Connection'
        self._poll_backoff = 5.0

    def _init_updater(self):
        """(Re)initialize telegram updater preserving handlers"""
        self.logger.debug("Reinitializing Telegram updater")
        old_updater = getattr(self, "updater", None)
        new_updater = Updater(token=self.token, use_context=True)
        if old_updater:
            try:
                for group, handlers in old_updater.dispatcher.handlers.items():
                    for handler in handlers:
                        new_updater.dispatcher.add_handler(handler, group)
            except Exception as exc:  # pylint:disable=broad-except
                self.logger.error("Failed to copy handlers: %s", repr(exc))
        self.updater = new_updater

    def send_message(self, *args, **kwargs):
        """
        Send Telegram message

        :param args:
        :param kwargs:
        :return:
        """
        retries = 0
        while retries < 5 and not self.exit:
            try:
                return self.updater.bot.send_message(*args, **kwargs)
            except NetworkError as exc:
                self.logger.error('Telegram network error: %s', repr(exc))
            except TelegramError as exc:  # pylint:disable=broad-except
                self.logger.error('Telegram error: %s', repr(exc))
            retries += 1
            time.sleep(5)
        self.logger.error('Failed to send Telegram message after retries')
        return None

    def send_reaction(self, chat_id: int, message_id: int, emoji: str, is_big: bool = False):
        """Attempt to set a Telegram reaction, fallback to textual reply if unavailable."""

        payload = {
            'chat_id': chat_id,
            'message_id': message_id,
            'reaction': [{'type': 'emoji', 'emoji': emoji}],
        }
        if is_big:
            payload['is_big'] = True

        try:
            self.updater.bot._post('setMessageReaction', data=payload, timeout=10)  # pylint:disable=protected-access
            return True, None
        except (NetworkError, TelegramError) as exc:  # pylint:disable=broad-except
            self.logger.warning('Falling back to textual reaction: %s', repr(exc))
        message = self.send_message(
            chat_id=chat_id,
            text=emoji,
            reply_to_message_id=message_id,
        )
        return False, message

    def poll(self) -> None:
        """
        Run Telegram bot polling

        :return:
        """
        setthreadtitle(self.name)
        while not self.exit:
            delay = None
            try:
                self.logger.debug("Starting Telegram polling loop")
                self.updater.start_polling()
                self._poll_backoff = 5.0

                while not self.exit:
                    time.sleep(1)
            except (NetworkError, TelegramError) as exc:
                delay = self._next_poll_delay(exc)
                self.logger.warning(
                    'Telegram polling error: %s; retrying in %.1f seconds',
                    repr(exc),
                    delay,
                    exc_info=True,
                )
                # recreate updater on errors to ensure handlers are registered
                self._init_updater()
            finally:
                try:
                    self.updater.stop()
                except Exception:  # pylint:disable=broad-except
                    self.logger.exception("Failed to stop updater")
                self.logger.debug("Telegram polling loop stopped")
            if self.exit:
                break
            if delay is None:
                time.sleep(1)
            else:
                time.sleep(delay)

    @property
    def dispatcher(self) -> telegram.ext.Dispatcher:
        """
        Return Telegram dispatcher for commands

        :return:
        """
        return self.updater.dispatcher

    def shutdown(self):
        """
        Stop Telegram bot
        """
        self.exit = True
        self.updater.stop()

    def _next_poll_delay(self, exc: Exception) -> float:
        """Return the next polling backoff delay based on the exception."""

        description = repr(exc)
        if any(text in description for text in ('Timed out', 'Connection reset by peer')):
            self._poll_backoff = min(self._poll_backoff * 2, 60.0)
        else:
            self._poll_backoff = min(self._poll_backoff + 5.0, 60.0)
        return self._poll_backoff

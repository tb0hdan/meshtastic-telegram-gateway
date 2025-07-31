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
        self.updater = Updater(token=token, use_context=True)
        self.exit = False
        self.name = 'Telegram Connection'

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

    def send_message(self, *args, **kwargs) -> None:
        """
        Send Telegram message

        :param args:
        :param kwargs:
        :return:
        """
        retries = 0
        while retries < 5 and not self.exit:
            try:
                self.updater.bot.send_message(*args, **kwargs)
                return
            except NetworkError as exc:
                self.logger.error('Telegram network error: %s', repr(exc))
            except TelegramError as exc:  # pylint:disable=broad-except
                self.logger.error('Telegram error: %s', repr(exc))
            retries += 1
            time.sleep(5)
        self.logger.error('Failed to send Telegram message after retries')

    def poll(self) -> None:
        """
        Run Telegram bot polling

        :return:
        """
        setthreadtitle(self.name)
        while not self.exit:
            try:
                self.logger.debug("Starting Telegram polling loop")
                self.updater.start_polling()

                while not self.exit:
                    time.sleep(1)
            except (NetworkError, TelegramError) as exc:
                self.logger.error('Telegram polling error: %s', repr(exc))
                # recreate updater on errors to ensure handlers are registered
                self._init_updater()
            finally:
                try:
                    self.updater.stop()
                except Exception:  # pylint:disable=broad-except
                    self.logger.exception("Failed to stop updater")
                self.logger.debug("Telegram polling loop stopped")
            time.sleep(10)

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

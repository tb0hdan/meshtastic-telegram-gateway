# -*- coding: utf-8 -*-
""" Telegram connection module """


import logging
import time

import telegram
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
        self.updater = Updater(token=token, use_context=True)
        self.exit = False
        self.name = 'Telegram Connection'

    def _init_updater(self):
        """(Re)initialize telegram updater"""
        self.updater = Updater(token=self.token, use_context=True)

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
                self._init_updater()
                self.updater.start_polling()

                while not self.exit:
                    time.sleep(1)
            except (NetworkError, TelegramError) as exc:
                self.logger.error('Telegram polling error: %s', repr(exc))
            finally:
                try:
                    self.updater.stop()
                except Exception:  # pylint:disable=broad-except
                    pass
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

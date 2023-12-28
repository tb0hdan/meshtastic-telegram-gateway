# -*- coding: utf-8 -*-
""" Telegram connection module """


import logging

import telegram
from telegram.ext import Updater


class TelegramConnection:
    """
    Telegram connection
    """

    def __init__(self, token: str, logger: logging.Logger):
        self.logger = logger
        self.updater = Updater(token=token, use_context=True)

    def send_message(self, *args, **kwargs) -> None:
        """
        Send Telegram message

        :param args:
        :param kwargs:
        :return:
        """
        self.updater.bot.send_message(*args, **kwargs)

    def poll(self) -> None:
        """
        Run Telegram bot polling

        :return:
        """
        self.updater.start_polling()

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
        self.updater.stop()

# -*- coding: utf-8 -*-
""" Telegram connection module """

import asyncio
import logging

from telegram import Update
from telegram.ext import Application


class TelegramConnection:
    """
    Telegram connection
    """

    def __init__(self, token: str, logger: logging.Logger):
        self.logger = logger
        logging.getLogger("httpx").setLevel(logging.WARNING)
        self.application = Application.builder().token(token).build()

    def send_message(self, *args, **kwargs) -> None:
        """
        Send a Telegram message

        :param args:
        :param kwargs:
        :return:
        """
        asyncio.run(self.application.bot.send_message(*args, **kwargs))

    def poll(self) -> None:
        """
        Run Telegram bot polling

        :return:
        """
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)

    def shutdown(self):
        """
        Stop Telegram bot
        """
        self.application.stop_running()

# -*- coding: utf-8 -*-
""" Slack bot module """
import logging
import time
import sys
from threading import Thread
# pylint:disable=no-name-in-module
from setproctitle import setthreadtitle
from slack_sdk.rtm_v2 import RTMClient

class SlackBot:
    """
    Slack bot class
    """
    def __init__(self, logger: logging.Logger):
        self.name = "SlackBot"
        self.logger = logger
        self.rtm = RTMClient(token="",
                             trace_enabled = True, logger = logger,
                             all_message_trace_enabled = True,
                             ping_pong_trace_enabled = True)

    def handle(self, _client: RTMClient, event: dict):
        """
        Event handler for the bot

        :param _client: RTMClient
        :param event: dict
        :return:
        """
        if not event.get('text'):
            return
        if 'Hello' in event['text']:
            channel_id = event['channel']
            # thread_ts = event['ts']
            user = event['user']  # This is not username but user ID (the format is either U*** or W***)

            self.send_text(channel_id, f"Hi <@{user}>!")

    def send_text(self, channel: str, text: str, thread_ts: str = None):
        """
        Send text to channel

        :param channel: str
        :param text: str
        :return:
        """
        self.rtm.web_client.chat_postMessage(
            channel=channel,
            text=text,
            thread_ts=thread_ts
        )

    def poll(self):
        """
        Polling method for the bot

        :return:
        """
        setthreadtitle(self.name)
        self.rtm.on("message")(self.handle)
        self.rtm.connect()
        while True:
            try:
                time.sleep(1)
            except KeyboardInterrupt:
                sys.exit(0)

    def run(self):
        """
        Telegram bot runner

        :return:
        """
        thread = Thread(target=self.poll, name=self.name)
        thread.start()

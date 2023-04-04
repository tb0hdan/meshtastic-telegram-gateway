# -*- coding: utf-8 -*-
""" MQTT connection module """

import socket
import time
#
from threading import Thread
#
import paho.mqtt.client as mqtt
# pylint:disable=no-name-in-module
from setproctitle import setthreadtitle
#


class MQTT:
    """
    MQTT - MQTT connection class
    """
    def __init__(self, host, user, password, logger, port=1883):  # pylint:disable=too-many-arguments
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.username_pw_set(user, password)
        #
        self.config = None
        #
        self.logger = logger
        # for connection
        self.host = host
        self.port = port
        # for processing
        self.handler = None
        #
        self.name = 'MQTT Connection'

    def set_config(self, config):
        """
        set_config - MQTT config setter

        :param config:
        :return:
        """
        self.config = config

    def on_connect(self, client, _userdata, _flags, result_code):
        """
        on_connect - MQTT callback for connection event

        :param client:
        :param _userdata:
        :param _flags:
        :param result_code:
        :return:
        """
        self.logger.info("Connected with result code "+str(result_code))
        client.subscribe('msh/#')

    def on_message(self, _client, _userdata, msg):
        """
        on_message - MQTT callback for message event

        :param _client:
        :param _userdata:
        :param msg:
        :return:
        """
        if self.handler is not None:
            self.handler(msg.topic, msg.payload)

    def set_handler(self, handler):
        """
        set_handler - MQTT handler setter

        :param handler:
        :return:
        """
        self.handler = handler

    def run_loop(self):
        """
        run_loop - MQTT loop runner

        :return:
        """
        setthreadtitle(self.name)
        while True:
            try:
                self.client.connect(self.host, self.port, 60)
            except socket.timeout:
                self.logger.error('Connect timeout...')
                time.sleep(10)
            try:
                self.client.loop_forever()
            except TimeoutError:
                self.logger.error('Loop timeout...')
                time.sleep(10)

    def run(self):
        """
        MQTT runner

        :return:
        """
        if self.config.enforce_type(bool, self.config.MQTT.Enabled):
            self.logger.info('Starting MQTT client...')
            thread = Thread(target=self.run_loop, daemon=True, name=self.name)
            thread.start()

# -*- coding: utf-8 -*-
""" MQTT connection module """

from threading import Thread
#
import paho.mqtt.client as mqtt
from .common import CommonMQTT

class MQTT:  # pylint:disable=too-many-instance-attributes
    """
    MQTT - MQTT connection class
    """
    def __init__(self, topic, host, user, password, logger, port=1883):  # pylint:disable=too-many-arguments
        self.topic = topic
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
        # exit
        self.exit = False
        #
        self.common = CommonMQTT(self.name)
        self.common.set_client(self.client)
        self.common.set_logger(logger)

    def set_config(self, config):
        """
        set_config - MQTT config setter

        :param config:
        :return:
        """
        self.config = config
        self.common.set_config(config)

    def on_connect(self, client, _userdata, _flags, result_code):
        """
        on_connect - MQTT callback for connection event

        :param client:
        :param _userdata:
        :param _flags:
        :param result_code:
        :return:
        """
        self.logger.info(f"Connected with result code {str(result_code)}")
        client.subscribe(f'{self.topic}/#')

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

    def shutdown(self):
        """
        shutdown - MQTT shutdown method
        """
        self.client.disconnect()
        self.exit = True
        self.common.set_exit(True)

    def run(self):
        """
        MQTT runner

        :return:
        """
        if self.config.enforce_type(bool, self.config.MQTT.Enabled):
            self.logger.info('Starting MQTT client...')
            thread = Thread(target=self.common.run_loop, daemon=True, name=self.name)
            thread.start()

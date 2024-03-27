#-*- coding: utf-8 -*-
""" MQTT to Radio emulation transport module """

import socket
import time

# pylint:disable=no-name-in-module
from setproctitle import setthreadtitle

class CommonMQTT: # pylint:disable=too-many-instance-attributes
    """
    CommonMQTT - Common MQTT connection class
    """
    def __init__(self, name = 'MQTT Connection'):
        self.host = None
        self.port = None
        self.user = None
        self.password = None
        self.logger = None
        self.client = None
        #
        self.name = name
        self.exit = False

    def set_exit(self, exit_value):
        """
        set_exit - exit setter

        :param exit_value:
        :return:
        """
        self.exit = exit_value

    def set_config(self, config):
        """
        set_config - MQTT config setter

        :param config:
        :return:
        """
        self.host = config.MQTT.Host
        self.port = int(config.MQTT.Port)
        self.user = config.MQTT.User
        self.password = config.MQTT.Password

    def set_client(self, client):
        """
        set_client - client setter

        :param client:
        :return:
        """
        self.client = client

    def set_logger(self, logger):
        """
        set_logger - logger setter

        :param logger:
        :return:
        """
        self.logger = logger

    def run_loop(self):
        """
        run_loop - MQTT loop runner

        :return:
        """
        setthreadtitle(self.name)
        print(f'Connecting to {self.host}:{self.port}...')
        while not self.exit:
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

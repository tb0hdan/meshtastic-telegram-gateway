import socket
import time
#
from threading import Thread
#
import paho.mqtt.client as mqtt
#
from mtg.config import Config


class MQTT:
    def __init__(self, host, user, password, logger, port=1883):
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

    def set_config(self, config):
        self.config = config

    def on_connect(self, client, userdata, flags, rc):
        self.logger.info("Connected with result code "+str(rc))
        client.subscribe('msh/#')

    def on_message(self, client, userdata, msg):
        self.logger.info(msg.topic+" "+str(msg.payload))

    def run_loop(self):
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
            thread = Thread(target=self.run_loop, daemon=True)
            thread.start()

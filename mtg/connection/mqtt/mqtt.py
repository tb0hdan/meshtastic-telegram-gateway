# -*- coding: utf-8 -*-
""" MQTT connection module """

from threading import Thread
from typing import Any, Callable, Optional
#
import paho.mqtt.client as mqtt
from .common import CommonMQTT

class MQTT:  # pylint:disable=too-many-instance-attributes
    """
    MQTT - MQTT connection class
    """
    # pylint:disable=too-many-arguments,too-many-positional-arguments
    def __init__(self, topic: str, host: str, user: str, password: str, logger: Any, port: int = 1883) -> None:
        self.topic = topic
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.username_pw_set(user, password)
        #
        self.config: Optional[Any] = None
        #
        self.logger = logger
        # for connection
        self.host = host
        self.port = port
        # for processing
        self.handler: Optional[Callable[[str, bytes], None]] = None
        #
        self.name = 'MQTT Connection'
        # exit
        self.exit = False
        #
        self.common = CommonMQTT(self.name)
        self.common.set_client(self.client)
        self.common.set_logger(logger)

    def set_config(self, config: Any) -> None:
        """
        set_config - MQTT config setter

        :param config:
        :return:
        """
        self.config = config
        self.common.set_config(config)

    def on_connect(self, client: Any, _userdata: Any, _flags: Any, result_code: int) -> None:
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

    def on_message(self, _client: Any, _userdata: Any, msg: Any) -> None:
        """
        on_message - MQTT callback for message event

        :param _client:
        :param _userdata:
        :param msg:
        :return:
        """
        if self.handler is not None:
            try:
                self.handler(msg.topic, msg.payload)
            except Exception as exc:  # pylint:disable=broad-exception-caught
                self.logger.error('An exception occured in self.handler: %s', repr(exc))

    def set_handler(self, handler: Callable[[str, bytes], None]) -> None:
        """
        set_handler - MQTT handler setter

        :param handler:
        :return:
        """
        self.handler = handler

    def shutdown(self) -> None:
        """
        shutdown - MQTT shutdown method
        """
        self.client.disconnect()
        self.exit = True
        self.common.set_exit(True)

    def run(self) -> None:
        """
        MQTT runner

        :return:
        """
        self.logger.info('Starting MQTT client...')
        thread = Thread(target=self.common.run_loop, daemon=True, name=self.name)
        thread.start()

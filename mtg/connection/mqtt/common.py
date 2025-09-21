#-*- coding: utf-8 -*-
""" MQTT to Radio emulation transport module """

import socket
import time
from typing import Any, Optional
# 3rd party
from setproctitle import setthreadtitle

class CommonMQTT: # pylint:disable=too-many-instance-attributes
    """
    CommonMQTT - Common MQTT connection class
    """
    def __init__(self, name: str = 'MQTT Connection') -> None:
        self.host: Optional[str] = None
        self.port: Optional[int] = None
        self.user: Optional[str] = None
        self.password: Optional[str] = None
        self.logger: Optional[Any] = None
        self.client: Optional[Any] = None
        #
        self.name = name
        self.exit = False

    def set_exit(self, exit_value: bool) -> None:
        """
        set_exit - exit setter

        :param exit_value:
        :return:
        """
        self.exit = exit_value

    def set_config(self, config: Any) -> None:
        """
        set_config - MQTT config setter

        :param config:
        :return:
        """
        self.host = config.MQTT.Host
        self.port = int(config.MQTT.Port)
        self.user = config.MQTT.User
        self.password = config.MQTT.Password

    def set_client(self, client: Any) -> None:
        """
        set_client - client setter

        :param client:
        :return:
        """
        self.client = client

    def set_logger(self, logger: Any) -> None:
        """
        set_logger - logger setter

        :param logger:
        :return:
        """
        self.logger = logger

    def run_loop(self) -> None:
        """
        run_loop - MQTT loop runner

        :return:
        """
        setthreadtitle(self.name)
        if self.logger:
            self.logger.info(f'Connecting to {self.host}:{self.port}...')
        while not self.exit:
            try:
                if self.client:
                    self.client.connect(self.host, self.port, 60)
            except socket.timeout:
                if self.logger:
                    self.logger.error('Connect timeout...')
                time.sleep(10)
            try:
                if self.client:
                    self.client.loop_forever()
            except TimeoutError:
                if self.logger:
                    self.logger.error('Loop timeout...')
                time.sleep(10)

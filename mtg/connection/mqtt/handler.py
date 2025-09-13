# -*- coding: utf-8 -*-
""" MQTT handler module """

from typing import Any, Callable, Optional

NODE_PREFIX = "!"


class MQTTHandler:
    """
    MQTTHandler - handles MQTT packets and does some specific filtering
    """

    def __init__(self, topic: str, logger: Any) -> None:
        self.topic = topic
        self.logger = logger
        self.node_callback: Optional[Callable[[str, str], None]] = None
        self.filter: Optional[Any] = None

    def handler(self, topic: str, payload: bytes) -> None:
        """
        handler - MQTT packet handler

        :param topic:
        :param payload:
        :return:
        """
        payload_str: str
        try:
            payload_str = payload.decode()
        except UnicodeDecodeError:
            payload_str = str(payload)
        if len(topic.split(NODE_PREFIX)) != 2:
            return
        node = NODE_PREFIX + topic.split(NODE_PREFIX)[1]
        if self.filter and self.filter.banned(node):
            self.logger.debug(f"User {node} is in a blacklist...")
            return
        if self.node_callback is not None and topic.startswith(f'{self.topic}/2/stat/'):
            self.node_callback(node, payload_str)

    def set_node_callback(self, callback: Callable[[str, str], None]) -> None:
        """
        set_node_callback - set up node callback

        :param callback:
        :return:
        """
        self.node_callback = callback

    def set_filter(self, filter_class: Any) -> None:
        """
        set_filter - set up filter class

        :param filter_class:
        :return:
        """
        self.filter = filter_class

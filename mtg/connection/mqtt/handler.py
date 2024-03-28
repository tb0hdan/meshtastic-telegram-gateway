# -*- coding: utf-8 -*-
""" MQTT handler module """

NODE_PREFIX = "!"


class MQTTHandler:
    """
    MQTTHandler - handles MQTT packets and does some specific filtering
    """

    def __init__(self, topic, logger):
        self.topic = topic
        self.logger = logger
        self.node_callback = None
        self.filter = None

    def handler(self, topic, payload):
        """
        handler - MQTT packet handler

        :param topic:
        :param payload:
        :return:
        """
        try:
            payload = payload.decode()
        except UnicodeDecodeError:
            payload = str(payload)
        if len(topic.split(NODE_PREFIX)) != 2:
            return
        node = NODE_PREFIX + topic.split(NODE_PREFIX)[1]
        if self.filter and self.filter.banned(node):
            self.logger.debug(f"User {node} is in a blacklist...")
            return
        if self.node_callback is not None and topic.startswith('{self.topic}/2/stat/'):
            self.node_callback(node, payload)

    def set_node_callback(self, callback):
        """
        set_node_callback - set up node callback

        :param callback:
        :return:
        """
        self.node_callback = callback

    def set_filter(self, filter_class):
        """
        set_filter - set up filter class

        :param filter_class:
        :return:
        """
        self.filter = filter_class

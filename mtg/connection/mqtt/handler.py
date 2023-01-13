# -*- coding: utf-8 -*-
""" MQTT handler module """


NODE_PREFIX = "!"

class MQTTHandler:
    """
    MQTTHandler - handles MQTT packets and does some specific filtering
    """
    def __init__(self, logger):
        self.logger = logger
        self.node_callback = None

    def handler(self, topic, payload):
        """
        handler - process MQTT payload and call assinged node callback
        """
        try:
            payload = payload.decode()
        except UnicodeDecodeError:
            payload = str(payload)
        if len(topic.split(NODE_PREFIX)) != 2:
            return
        node = NODE_PREFIX + topic.split(NODE_PREFIX)[1]
        if self.node_callback is not None and topic.startswith('msh/2/stat/'):
            self.node_callback(node, payload)

    def set_node_callback(self, callback):
        """
        set_node_callback - node callback function setter
        """
        self.node_callback = callback

NODE_PREFIX = "!"

class MQTTHandler:
    def __init__(self, logger):
        self.logger = logger
        self.node_callback = None

    def handler(self, topic, payload):
        self.logger.info(topic+" "+str(payload))
        if len(topic.split(NODE_PREFIX)) != 2:
            return
        node = NODE_PREFIX + topic.split(NODE_PREFIX)[1]
        if self.node_callback is not None:
            self.node_callback(node)

    def set_node_callback(self, callback):
        self.node_callback = callback

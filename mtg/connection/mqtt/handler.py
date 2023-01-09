class MQTTHandler:
    def __init__(self, logger):
        self.logger = logger

    def handler(self, topic, payload):
        self.logger.info(topic+" "+str(payload))

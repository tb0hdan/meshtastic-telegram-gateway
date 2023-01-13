import errno
import logging
import os
import sys
import time
#
from threading import Thread
from typing import (
    Dict,
    List,
)
#
from meshtastic import (
    LOCAL_ADDR as MESHTASTIC_LOCAL_ADDR,
    BROADCAST_ADDR as MESHTASTIC_BROADCAST_ADDR,
    serial_interface as meshtastic_serial_interface,
    tcp_interface as meshtastic_tcp_interface,
)

FIFO = '/tmp/mtg.fifo'

class MeshtasticConnection:
    """
    Meshtastic device connection
    """

    def __init__(self, dev_path: str, logger: logging.Logger, config, startup_ts = time.time()):
        self.dev_path = dev_path
        self.interface = None
        self.logger = logger
        self.config = config
        self.startup_ts = startup_ts
        self.mqtt_nodes = {}

    @property
    def get_startup_ts(self):
        """
        get_startup_ts - returns Unix timestamp since startup
        """
        return self.startup_ts

    def connect(self):
        """
        Connect to Meshtastic device. Interface can be later updated during reboot procedure

        :return:
        """
        if not self.dev_path.startswith('tcp:'):
            self.interface = meshtastic_serial_interface.SerialInterface(devPath=self.dev_path, debugOut=sys.stdout)
        else:
            self.interface = meshtastic_tcp_interface.TCPInterface(self.dev_path.lstrip('tcp:'), debugOut=sys.stdout)

    def send_text(self, *args, **kwargs) -> None:
        """
        Send Meshtastic message

        :param args:
        :param kwargs:
        :return:
        """
        self.interface.sendText(*args, **kwargs)

    def node_info(self, node_id) -> Dict:
        """
        Return node information for a specific node ID

        :param node_id:
        :return:
        """
        return self.interface.nodes.get(node_id, {})

    def reboot(self):
        """
        Execute Meshtastic device reboot

        :return:
        """
        self.logger.info("Reboot requested...")
        self.interface.getNode(MESHTASTIC_LOCAL_ADDR).reboot(10)
        self.interface.close()
        time.sleep(20)
        self.connect()
        self.logger.info("Reboot completed...")

    def reset_db(self):
        self.logger.info('Reset node DB requested...')
        self.interface.getNode(MESHTASTIC_LOCAL_ADDR, False).resetNodeDb()
        self.logger.info('Reset node DB completed...')

    def on_mqtt_node(self, node_id, payload):
        self.logger.debug(f'{node_id} is {payload}')
        self.mqtt_nodes[node_id] = payload

    @property
    def nodes_mqtt(self) -> List:
        return [node_id for node_id in self.mqtt_nodes]

    def node_has_mqtt(self, node_id):
        return node_id in self.mqtt_nodes

    def node_mqtt_status(self, node_id):
        return self.mqtt_nodes.get(node_id, 'N/A')

    @property
    def nodes(self) -> Dict:
        """
        Return dictionary of nodes

        :return:
        """
        return self.interface.nodes if self.interface.nodes else {}

    @property
    def nodes_with_info(self) -> List:
        """
        Return list of nodes with information

        :return:
        """
        node_list = []
        for node in self.nodes:
            node_list.append(self.nodes.get(node))
        return node_list

    @property
    def nodes_with_position(self) -> List:
        """
        Filter out nodes without position

        :return:
        """
        node_list = []
        for node_info in self.nodes_with_info:
            if not node_info.get('position'):
                continue
            node_list.append(node_info)
        return node_list

    @property
    def nodes_with_user(self) -> List:
        """
        Filter out nodes without position or user

        :return:
        """
        node_list = []
        for node_info in self.nodes_with_position:
            if not node_info.get('user'):
                continue
            node_list.append(node_info)
        return node_list

    def run_loop(self):
        try:
            os.mkfifo(FIFO)
        except OSError as exc:
            if exc.errno != errno.EEXIST:
                raise

        self.logger.debug("Opening FIFO...")
        while True:
            with open(FIFO) as fifo:
                for line in fifo:
                    line = line.rstrip('\n')
                    self.send_text(line, destinationId=MESHTASTIC_BROADCAST_ADDR)

    def run(self):
        """
        Meshtastic connection runner

        :return:
        """
        if self.config.enforce_type(bool, self.config.Meshtastic.FIFOEnabled):
            thread = Thread(target=self.run_loop, daemon=True)
            thread.start()

# -*- coding: utf-8 -*-
""" Meshtastic connection module """

import logging
import re
import sys
import time
#
from threading import RLock, Thread
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
    mesh_pb2
)
from setproctitle import setthreadtitle

from mtg.utils import create_fifo, split_message


FIFO = '/tmp/mtg.fifo'

# pylint:disable=too-many-instance-attributes
class MeshtasticConnection:
    """
    Meshtastic device connection
    """
    # pylint:disable=too-many-arguments
    def __init__(self, dev_path: str, logger: logging.Logger, config, filter_class, startup_ts = time.time()):
        self.dev_path = dev_path
        self.interface = None
        self.logger = logger
        self.config = config
        self.startup_ts = startup_ts
        self.mqtt_nodes = {}
        self.name = 'Meshtastic Connection'
        self.lock = RLock()
        self.filter = filter_class

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

    def send_text(self, msg, **kwargs) -> None:
        """
        Send Meshtastic message

        :param args:
        :param kwargs:
        :return:
        """
        if len(msg) < mesh_pb2.Constants.DATA_PAYLOAD_LEN // 2:
            with self.lock:
                self.interface.sendText(msg, **kwargs)
                return
        split_message(msg, mesh_pb2.Constants.DATA_PAYLOAD_LEN // 2, self.send_text, **kwargs)
        return

    def send_data(self, *args, **kwargs) -> None:
        """
        Send Meshtastic data message

        :param args:
        :param kwargs:
        :return:
        """
        with self.lock:
            self.interface.sendData(*args, **kwargs)

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
        """
        reset_db - reset Meshtastic device internal node table
        """
        self.logger.info('Reset node DB requested...')
        self.interface.getNode(MESHTASTIC_LOCAL_ADDR, False).resetNodeDb()
        self.logger.info('Reset node DB completed...')

    def on_mqtt_node(self, node_id, payload):
        """
        on_mqtt_node - update node info when MQTT payload arrives. Callback method
        """
        self.logger.debug(f'{node_id} is {payload}')
        self.mqtt_nodes[node_id] = payload

    @property
    def nodes_mqtt(self) -> List:
        """
        nodes_mqtt - getter for node list from MQTT
        """
        return list(self.mqtt_nodes)

    def node_has_mqtt(self, node_id):
        """
        node_has_mqtt - return MQTT status for node. Boolean
        """
        return node_id in self.mqtt_nodes

    def node_mqtt_status(self, node_id):
        """
        node_mqtt_status - return MQTT status for node. String
        """
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

    # pylint:disable=too-many-branches
    def format_nodes(self, include_self=False):
        """
        Formats node list to be more compact

        :param nodes:
        :return:
        """
        table = self.interface.showNodes(includeSelf=include_self)
        if not table:
            return "No other nodes"

        nodes = re.sub(r'[╒═╤╕╘╧╛╞╪╡├─┼┤]', '', table)
        nodes = nodes.replace('│', ',')
        new_nodes = []
        header = True
        for line in nodes.split('\n'):
            line = line.lstrip(',').rstrip(',').rstrip('\n')
            if not line:
                continue
            # clear column value
            i = 0
            new_line = []
            for column in line.split(','):
                column = column.strip()
                if i == 0:
                    if not header:
                        column = f'**{column}**`'
                    else:
                        column = f'**{column}**'.replace('.', r'\.')
                new_line.append(column + ', ')
                if not header:
                    i += 1
            reassembled_line = ''.join(new_line).rstrip(', ')
            if not header:
                reassembled_line = f'{reassembled_line}`'
            else:
                reassembled_line = f'{reassembled_line}'
            header = False
            new_nodes.append(reassembled_line)
        filtered_nodes = []
        for line in new_nodes:
            node_id = line.split(', ')[3]
            if not node_id.startswith('!'):
                continue
            if self.filter.banned(node_id):
                self.logger.debug(f"Node {node_id} is in a blacklist...")
                continue
            filtered_nodes.append(line)
        return '\n'.join(new_nodes)

    def run_loop(self):
        """
        Meshtastic loop runner. Used for messages

        :return:
        """
        setthreadtitle(self.name)

        self.logger.debug("Opening FIFO...")
        create_fifo(FIFO)
        while True:
            with open(FIFO, encoding='utf-8') as fifo:
                for line in fifo:
                    line = line.rstrip('\n')
                    self.send_text(line, destinationId=MESHTASTIC_BROADCAST_ADDR)

    def run(self):
        """
        Meshtastic connection runner

        :return:
        """
        if self.config.enforce_type(bool, self.config.Meshtastic.FIFOEnabled):
            thread = Thread(target=self.run_loop, daemon=True, name=self.name)
            thread.start()

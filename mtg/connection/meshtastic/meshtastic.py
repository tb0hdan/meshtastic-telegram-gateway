# -*- coding: utf-8 -*-
""" Meshtastic connection module """

import logging
import re
import sys
import time
import json
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
# pylint:disable=no-name-in-module
from meshtastic.protobuf import config_pb2
# pylint:disable=no-name-in-module,no-member
from setproctitle import setthreadtitle

from mtg.utils import create_fifo, split_message, split_user_message
from mtg.connection.mqtt import MQTTInterface

FIFO = '/tmp/mtg.fifo'
FIFO_CMD = '/tmp/mtg.cmd.fifo'


# pylint:disable=too-many-instance-attributes,too-many-public-methods
class MeshtasticConnection:
    """
    Meshtastic device connection
    """

    # pylint:disable=too-many-arguments,too-many-positional-arguments
    def __init__(self, dev_path: str, logger: logging.Logger, config, filter_class, startup_ts=time.time()):
        self.dev_path = dev_path
        self.interface = None
        self.logger = logger
        self.config = config
        self.startup_ts = startup_ts
        self.mqtt_nodes = {}
        self.name = 'Meshtastic Connection'
        self.lock = RLock()
        self.filter = filter_class
        # exit
        self.exit = False

    @property
    def get_startup_ts(self):
        """
        Get startup timestamp

        :return:
        """
        return self.startup_ts

    def _connect_once(self):
        if self.dev_path.startswith('tcp:'):
            self.interface = meshtastic_tcp_interface.TCPInterface(
                self.dev_path.removeprefix('tcp:'), debugOut=sys.stdout
            )
        elif self.dev_path == 'mqtt':
            self.interface = MQTTInterface(debugOut=sys.stdout, cfg=self.config, logger=self.logger)
        else:
            self.interface = meshtastic_serial_interface.SerialInterface(
                devPath=self.dev_path, debugOut=sys.stdout
            )

    def connect(self):
        """Connect to Meshtastic device with retries"""
        retries = 0
        last_exc = None
        while retries < 3:
            try:
                self._connect_once()
                return
            except Exception as exc:  # pylint:disable=broad-except
                last_exc = exc
                self.logger.error("Meshtastic connect error: %s", repr(exc))
                if self.interface:
                    try:
                        self.interface.close()
                    except Exception as close_exc:  # pylint:disable=broad-except
                        self.logger.warning("Failed to close interface: %s", repr(close_exc))
                    self.interface = None
                retries += 1
                time.sleep(5)
        if last_exc:
            raise last_exc


    def send_text(self, msg, **kwargs) -> None:
        """
        Send Meshtastic message

        :param args:
        :param kwargs:
        :return:
        """
        log_data = {
            "event": "send_mesh",
            "message": msg,
            "kwargs": kwargs,
        }
        self.logger.info(json.dumps(log_data))
        if len(msg) < mesh_pb2.Constants.DATA_PAYLOAD_LEN // 2:  # pylint:disable=no-member
            with self.lock:
                self.interface.sendText(msg, **kwargs)
                return
        # pylint:disable=no-member
        split_message(msg, mesh_pb2.Constants.DATA_PAYLOAD_LEN // 2, self.interface.sendText, **kwargs)
        return

    def send_user_text(self, sender: str, message: str, **kwargs) -> None:
        """Send text message from a specific sender with automatic splitting"""

        chunk_len = mesh_pb2.Constants.DATA_PAYLOAD_LEN // 2  # pylint:disable=no-member
        full = f"{sender}: {message}"
        if len(full) <= chunk_len:
            self.send_text(full, **kwargs)
            return
        parts = split_user_message(sender, message, chunk_len)
        for part in parts:
            self.send_text(part, **kwargs)

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
        Reset Meshtastic device DB

        :return:
        """
        self.logger.info('Reset node DB requested...')
        self.interface.getNode(MESHTASTIC_LOCAL_ADDR).resetNodeDb()
        self.logger.info('Reset node DB completed...')

    # pylint:disable=too-many-locals,too-many-branches,too-many-statements
    def reset_params(self):
        """Reset device parameters to configured values.

        The device reboots after configuration is applied, which is expected.
        """
        if not self.config.enforce_type(
            bool, getattr(self.config.MeshtasticReset, 'Enabled', 'false')
        ):
            return
        try:
            self.interface.waitForConfig()
        except Exception as exc:  # pylint:disable=broad-except
            self.logger.error('Could not fetch device config: %s', repr(exc))
            return

        node = self.interface.getNode(MESHTASTIC_LOCAL_ADDR)
        diffs = []

        use_room = self.config.enforce_type(
            bool,
            getattr(self.config.MeshtasticReset, 'LongNameFromRoomLink', 'true'),
        )
        desired_long = (
            self.config.Telegram.RoomLink
            if use_room
            else getattr(self.config.MeshtasticReset, 'LongName', None)
        )
        desired_short = getattr(self.config.MeshtasticReset, 'ShortName', '🔗')
        current_long = self.interface.getLongName() or ''
        current_short = self.interface.getShortName() or ''
        if (desired_long and desired_long != current_long) or (
            desired_short and desired_short != current_short
        ):
            diffs.append(
                f'name {current_long}/{current_short} -> {desired_long}/{desired_short}'
            )
            node.setOwner(long_name=desired_long, short_name=desired_short)

        lora = node.localConfig.lora
        lora_changed = False
        if hasattr(self.config.MeshtasticReset, 'HopLimit'):
            hop_limit = self.config.enforce_type(
                int, self.config.MeshtasticReset.HopLimit
            )
            if lora.hop_limit != hop_limit:
                diffs.append(f'hop_limit {lora.hop_limit}->{hop_limit}')
                lora.hop_limit = hop_limit
                lora_changed = True
        if hasattr(self.config.MeshtasticReset, 'Region'):
            try:
                region_enum = config_pb2.Config.LoRaConfig.RegionCode.Value(
                    self.config.MeshtasticReset.Region
                )
                if lora.region != region_enum:
                    diffs.append(
                        f'region {lora.region}->{self.config.MeshtasticReset.Region}'
                    )
                    lora.region = region_enum
                    lora_changed = True
            except Exception as exc:  # pylint:disable=broad-except
                self.logger.error('Invalid region %s: %s', self.config.MeshtasticReset.Region, repr(exc))
        if hasattr(self.config.MeshtasticReset, 'DutyCycle'):
            duty = self.config.enforce_type(
                bool, self.config.MeshtasticReset.DutyCycle
            )
            if lora.override_duty_cycle != duty:
                diffs.append(f'duty_cycle {lora.override_duty_cycle}->{duty}')
                lora.override_duty_cycle = duty
                lora_changed = True
        if lora_changed:
            node.writeConfig('lora')

        if hasattr(self.config.MeshtasticReset, 'Role'):
            try:
                role_enum = config_pb2.Config.DeviceConfig.Role.Value(
                    self.config.MeshtasticReset.Role
                )
                device_cfg = node.localConfig.device
                if device_cfg.role != role_enum:
                    diffs.append(
                        f'role {device_cfg.role}->{self.config.MeshtasticReset.Role}'
                    )
                    device_cfg.role = role_enum
                    node.writeConfig('device')
            except Exception as exc:  # pylint:disable=broad-except
                self.logger.error('Invalid role %s: %s', self.config.MeshtasticReset.Role, repr(exc))

        if hasattr(self.config.MeshtasticReset, 'MapReporting'):
            try:
                map_report = self.config.enforce_type(
                    bool, self.config.MeshtasticReset.MapReporting
                )
                module_cfg = node.moduleConfig
                if module_cfg.mqtt.map_reporting_enabled != map_report:
                    diffs.append(
                        f'map_reporting {module_cfg.mqtt.map_reporting_enabled}->{map_report}'
                    )
                    module_cfg.mqtt.map_reporting_enabled = map_report
                    node.writeConfig('mqtt')
            except Exception as exc:  # pylint:disable=broad-except
                self.logger.error('Failed to set map reporting: %s', repr(exc))

        for diff in diffs:
            self.logger.info('Reset parameter: %s', diff)

    def on_mqtt_node(self, node_id, payload):
        """
        on_mqtt_node - callback for MQTT node status

        :param node_id:
        :param payload:
        :return:
        """
        self.logger.debug(f'{node_id} is {payload}')
        self.mqtt_nodes[node_id] = payload

    @property
    def nodes_mqtt(self) -> List:
        """
        Return list of nodes with MQTT status

        :return:
        """
        return list(self.mqtt_nodes)

    def node_has_mqtt(self, node_id):
        """
        node_has_mqtt - check if node has MQTT status

        :param node_id:
        :return:
        """
        return node_id in self.mqtt_nodes

    def node_mqtt_status(self, node_id):
        """
        node_mqtt_status - return MQTT status for a specific node ID

        :param node_id:
        :return:
        """
        return self.mqtt_nodes.get(node_id, 'N/A')

    @property
    def nodes(self) -> Dict:
        """
        Return dictionary of nodes

        :return:
        """
        return self.interface.nodes or {}

    @property
    def nodes_with_info(self) -> List:
        """
        Return list of nodes with information

        :return:
        """
        return [self.nodes.get(node) for node in self.nodes]

    @property
    def nodes_with_position(self) -> List:
        """
        Filter out nodes without position

        :return:
        """
        return [
            node_info
            for node_info in self.nodes_with_info
            if node_info.get('position')
        ]

    @property
    def nodes_with_user(self) -> List:
        """
        Filter out nodes without position or user

        :return:
        """
        return [
            node_info
            for node_info in self.nodes_with_position
            if node_info.get('user')
        ]

    # pylint:disable=too-many-branches
    def format_nodes(self, include_self=False):
        """
        Formats node list to be more compact

        :param include_self:
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
                    column = f'**{column}**'.replace('.', r'\.') if header else f'**{column}**`'
                new_line.append(f'{column}, ')
                if not header:
                    i += 1
            reassembled_line = ''.join(new_line).rstrip(', ')
            reassembled_line = f'{reassembled_line}' if header else f'{reassembled_line}`'
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
        while not self.exit:
            with open(FIFO, encoding='utf-8') as fifo:
                for line in fifo:
                    line = line.rstrip('\n')
                    self.send_text(line, destinationId=MESHTASTIC_BROADCAST_ADDR)

    def run_cmd_loop(self):
        """
        Meshtastic loop runner. Used for commands

        :return:
        """
        setthreadtitle("MeshtasticCmd")

        self.logger.debug("Opening FIFO...")
        create_fifo(FIFO_CMD)
        while not self.exit:
            with open(FIFO_CMD, encoding='utf-8') as fifo:
                for line in fifo:
                    line = line.rstrip('\n')
                    if line.startswith("reboot"):
                        self.logger.warning("Reboot requested using CMD...")
                        self.reboot()
                    if line.startswith("reset_db"):
                        self.logger.warning("Reset DB requested using CMD...")
                        self.reset_db()

    def shutdown(self):
        """
        Stop Meshtastic connection
        """
        self.exit = True

    def run(self):
        """
        Meshtastic connection runner

        :return:
        """
        if self.config.enforce_type(bool, self.config.Meshtastic.FIFOEnabled):
            thread = Thread(target=self.run_loop, daemon=True, name=self.name)
            thread.start()
            cmd_thread = Thread(target=self.run_cmd_loop, daemon=True, name="MeshtasticCmd")
            cmd_thread.start()

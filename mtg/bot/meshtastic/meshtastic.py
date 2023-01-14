# -*- coding: utf-8 -*-
""" Meshtastic bot module """


import logging
import time

import humanize

from meshtastic import (
    BROADCAST_ADDR as MESHTASTIC_BROADCAST_ADDR,
    serial_interface as meshtastic_serial_interface,
    portnums_pb2 as meshtastic_portnums_pb2
)

from pubsub import pub

from mtg.config import Config
from mtg.connection.meshtastic import MeshtasticConnection
from mtg.connection.telegram import TelegramConnection
from mtg.database import MeshtasticDB
from mtg.filter import MeshtasticFilter
from mtg.geo import get_lat_lon_distance
from mtg.log import VERSION
from mtg.output.file import CSVFileWriter

class MeshtasticBot: # pylint:disable=too-many-instance-attributes
    """
    Meshtastic bot
    """
    def __init__(self, database: MeshtasticDB, config: Config, meshtastic_connection: MeshtasticConnection,
                 telegram_connection: TelegramConnection):
        self.database = database
        self.config = config
        self.filter = None
        self.logger = None
        self.telegram_connection = telegram_connection
        self.meshtastic_connection = meshtastic_connection
        # track ping request/reply
        self.ping_container = {}
        # file logger
        self.writer = CSVFileWriter(dst=self.config.enforce_type(str, self.config.Meshtastic.NodeLogFile))

    def set_logger(self, logger: logging.Logger):
        """
        Set class logger

        :param logger:
        :return:
        """
        self.logger = logger
        self.writer.set_logger(self.logger)

    def set_filter(self, filter_class: MeshtasticFilter):
        """
        Set filter class

        :param filter_class:
        :return:
        """
        self.filter = filter_class

    def on_connection(self, interface: meshtastic_serial_interface.SerialInterface, topic=pub.AUTO_TOPIC) -> None:
        """
        on radio connection event

        :param interface:
        :param topic:
        :return:
        """
        self.logger.debug("connection on %s topic %s", interface, topic)

    def on_node_info(self, node, interface: meshtastic_serial_interface.SerialInterface) -> None:
        """
        on node information event

        :param node:
        :param interface:
        :return:
        """
        self.logger.debug("node info %s on interface %s", node, interface)

    def subscribe(self) -> None:
        """
        Subscribe to Meshtastic events

        :return:
        """
        pub.subscribe(self.on_receive, "meshtastic.receive")
        pub.subscribe(self.on_connection, "meshtastic.connection.established")
        pub.subscribe(self.on_connection, "meshtastic.connection.lost")

    @staticmethod
    def process_distance_command(packet, interface: meshtastic_serial_interface.SerialInterface) -> None:  # pylint:disable=too-many-locals
        """
        Process /distance Meshtastic command

        :param packet:
        :param interface:
        :return:
        """
        from_id = packet.get('fromId')
        mynode_info = interface.nodes.get(from_id)
        if not mynode_info:
            interface.sendText("distance err: no node info", destinationId=from_id)
            return
        position = mynode_info.get('position', {})
        if not position:
            interface.sendText("distance err: no position", destinationId=from_id)
            return
        my_latitude = position.get('latitude')
        my_longitude = position.get('longitude')
        if not (my_latitude and my_longitude):
            interface.sendText("distance err: no lat/lon", destinationId=from_id)
            return
        for node in interface.nodes:
            node_info = interface.nodes.get(node)
            position = node_info.get('position', {})
            if not position:
                continue
            latitude = position.get('latitude')
            longitude = position.get('longitude')
            if not (latitude and longitude):
                continue
            user = node_info.get('user', {})
            if not user:
                continue
            node_id = user.get('id', '')
            if from_id == node_id:
                continue
            long_name = user.get('longName', '')
            distance = round(get_lat_lon_distance((my_latitude, my_longitude), (latitude, longitude)))
            distance = humanize.intcomma(distance)
            msg = f"{long_name}: {distance}m"
            interface.sendText(msg, destinationId=from_id)

    def process_ping_command(self, packet, interface: meshtastic_serial_interface.SerialInterface) -> None:
        """
        Process /ping Meshtastic command

        :param packet:
        :param interface:
        :return:
        """
        from_id = packet.get('fromId')
        self.ping_container[from_id] = {'timestamp': time.time()}
        payload = str.encode("test string")
        interface.sendData(payload,
                           MESHTASTIC_BROADCAST_ADDR,
                           portNum=meshtastic_portnums_pb2.PortNum.REPLY_APP,
                           wantAck=True, wantResponse=True)

    # pylint: disable=unused-argument
    def process_stats_command(self, packet, interface: meshtastic_serial_interface.SerialInterface) -> None:
        """
        Process /stats Meshtastic command

        :param packet:
        :param _:
        :return:
        """
        from_id = packet.get('fromId')
        msg = self.database.get_stats(from_id)
        self.meshtastic_connection.send_text(msg, destinationId=from_id)


    def process_meshtastic_command(self, packet, interface: meshtastic_serial_interface.SerialInterface) -> None:
        """
        Process Meshtastic command

        :param packet:
        :param interface:
        :return:
        """
        decoded = packet.get('decoded')
        from_id = packet.get('fromId')
        msg = decoded.get('text', '')
        if msg.startswith('/distance'):
            self.process_distance_command(packet, interface)
            return
        if msg.startswith('/ping'):
            self.process_ping_command(packet, interface)
            return
        if msg.startswith('/stats'):
            self.process_stats_command(packet, interface)
            return
        if msg.startswith('/reboot') and from_id == self.config.Meshtastic.Admin:
            self.meshtastic_connection.reboot()
            return
        if msg.startswith('/reset_db') and from_id == self.config.Meshtastic.Admin:
            self.meshtastic_connection.reset_db()
            return
        self.meshtastic_connection.send_text("unknown command", destinationId=from_id)

    def process_uptime(self, packet, interface: meshtastic_serial_interface.SerialInterface) -> None:
        """
        process_uptime - return bot uptime
        """
        firmware = 'unknown'
        if interface.myInfo:
            firmware = interface.myInfo.firmware_version
        from_id = packet.get('fromId')
        formatted_time = humanize.naturaltime(time.time() - self.meshtastic_connection.get_startup_ts)
        self.meshtastic_connection.send_text(f'Bot v{VERSION}/FW: {firmware} started {formatted_time}',
                                             destinationId=from_id)

    def process_pong(self, packet) -> None:
        """

        :param packet:
        :return:
        """
        from_id = packet.get('fromId')
        to_id = packet.get('toId')
        rx_time = packet.get('rxTime', 0)
        rx_snr = packet.get('rxSnr', 0)
        processing_time = time.time() - rx_time
        # node info
        node_info = self.meshtastic_connection.node_info(to_id)
        user_info = node_info.get('user', {})
        remote_name = user_info.get('longName', to_id)
        #
        if self.ping_container.get(from_id, {}):
            timestamp = self.ping_container[from_id].get('timestamp', 0)
            processing_time += time.time() - timestamp
        msg = f"Pong from {remote_name} at {rx_snr:.2f} SNR, time={processing_time:.3f}s"
        self.meshtastic_connection.send_text(msg, destinationId=from_id)

    def notify_on_new_node(self, packet, interface: meshtastic_serial_interface.SerialInterface) -> None:
        """
        notify_on_new_node - sends notification about newly connected Meshtastic node (just once)

        :param packet:
        :param interface:
        :return:
        """
        from_id = packet.get('fromId')
        found, _ = self.database.get_node_record(from_id)
        # not a new node
        if found:
            return
        node_info = interface.nodes.get(from_id)
        if not node_info:
            return
        user_info = node_info.get('user')
        long_name = user_info.get('longName')
        # use map URL
        if self.config.enforce_type(bool, self.config.Telegram.MapLinkEnabled):
            map_link = self.config.Telegram.MapLink
            long_name = long_name.replace(' ', '%20')
            if '?tail=' in map_link:
                long_name = f'{map_link}&name={long_name}'
            else:
                long_name = f'{map_link}?name={long_name}'
        msg = f"{from_id} -> {long_name}"
        self.telegram_connection.send_message(chat_id=self.config.enforce_type(int,
                                                                               self.config.Telegram.NotificationsRoom),
                                              text=f"New node: {msg}")

    def on_receive(self, packet, interface: meshtastic_serial_interface.SerialInterface) -> None:
        """
        onReceive is called when a packet arrives

        :param packet:
        :param interface:
        :return:
        """
        self.logger.debug(f"Received: {packet}")
        to_id = packet.get('toId')
        decoded = packet.get('decoded')
        from_id = packet.get('fromId')
        # Send notifications if they're enabled
        if from_id is not None and self.config.enforce_type(bool, self.config.Telegram.NotificationsEnabled):
            self.notify_on_new_node(packet, interface)
        #
        if decoded.get('portnum') != 'TEXT_MESSAGE_APP':
            # notifications
            if decoded.get('portnum') == 'POSITION_APP':
                # Log if writer is enabled
                if from_id is not None and self.config.enforce_type(bool, self.config.Meshtastic.NodeLogEnabled):
                    self.writer.write(packet)
                self.database.store_location(packet)
                return
            # pong
            if decoded.get('portnum') == 'REPLY_APP':
                self.process_pong(packet)
                return
            return
        # ignore non-broadcast messages
        if to_id != MESHTASTIC_BROADCAST_ADDR:
            return
        # Save messages
        try:
            self.database.store_message(packet)
        except Exception as exc: # pylint:disable=broad-except
            self.logger.error('Could not store message: ', exc, repr(exc))
        # Process commands and forward messages
        node_info = interface.nodes.get(from_id)
        long_name = from_id
        if node_info is not None:
            user_info = node_info.get('user')
            long_name = user_info.get('longName')
        msg = decoded.get('text', '')
        # skip commands
        if msg.startswith('/'):
            self.process_meshtastic_command(packet, interface)
            return
        self.telegram_connection.send_message(chat_id=self.config.enforce_type(int, self.config.Telegram.Room),
                                              text=f"{long_name}: {msg}")

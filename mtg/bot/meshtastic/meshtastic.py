# -*- coding: utf-8 -*-
""" Meshtastic bot module """

import logging
import pkg_resources
import re
import time
import json

import humanize
import requests

from meshtastic import (
    BROADCAST_ADDR as MESHTASTIC_BROADCAST_ADDR,
    serial_interface as meshtastic_serial_interface,
    portnums_pb2 as meshtastic_portnums_pb2
)

from pubsub import pub

from mtg.config import Config
from mtg.connection.rich import RichConnection
from mtg.connection.telegram import TelegramConnection
from mtg.database import (
    MeshtasticDB,
    MESSAGE_DIRECTION_MESH_TO_TELEGRAM,
)
from mtg.filter import MeshtasticFilter
from mtg.geo import get_lat_lon_distance, deg_to_cardinal
from mtg.log import VERSION
from mtg.output.file import CSVFileWriter
from mtg.utils import Memcache


class MeshtasticBot:  # pylint:disable=too-many-instance-attributes
    """
    Meshtastic bot class
    """

    # pylint:disable=too-many-arguments,too-many-positional-arguments
    def __init__(self, database: MeshtasticDB, config: Config, meshtastic_connection: RichConnection,
                 telegram_connection: TelegramConnection, bot_handler):
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
        # bot
        self.bot_handler = bot_handler
        # aprs
        self.aprs = None
        # cache
        self.memcache = Memcache(self.logger)
        self.memcache.run_noblock()
        # cache of last battery readings per node to avoid duplicates
        self.battery_cache = {}

    def set_aprs(self, aprs):
        """
        Set APRS connection
        """
        self.aprs = aprs

    def set_logger(self, logger: logging.Logger):
        """
        Set logger

        :param logger:
        :return:
        """
        self.logger = logger
        self.memcache.set_logger(logger)
        self.writer.set_logger(self.logger)
        self._deliver_pending_mesh_messages()

    def set_filter(self, filter_class: MeshtasticFilter):
        """
        Set filter class

        :param filter_class:
        :return:
        """
        self.filter = filter_class

    def _deliver_pending_mesh_messages(self) -> None:
        """Attempt to resend pending Meshtastic-to-Telegram messages."""

        try:
            pending = list(self.database.iter_pending_links(MESSAGE_DIRECTION_MESH_TO_TELEGRAM))
        except Exception as exc:  # pylint:disable=broad-except
            self.logger.error('Failed to load pending Meshtastic messages: %s', repr(exc))
            return

        for record in pending:
            try:
                self._resend_pending_mesh_record(record)
            except Exception as exc:  # pylint:disable=broad-except
                self.logger.error('Pending Meshtastic message %s failed: %s', record.id, repr(exc))
                self.database.mark_link_retry(record.id, repr(exc))

    def _resend_pending_mesh_record(self, record) -> None:
        """Resend a single pending Meshtastic-originated record."""

        reply_message_id = None
        if record.reply_to_packet_id is not None:
            reply_link = self.database.get_link_by_meshtastic(record.reply_to_packet_id)
            if reply_link and reply_link.telegram_message_id:
                reply_message_id = reply_link.telegram_message_id
            else:
                self.database.mark_link_retry(record.id, 'missing Telegram mapping for reply')
                return

        chat_id = self.config.enforce_type(int, self.config.Telegram.Room)
        if record.emoji is not None and (record.payload is None or record.payload == ''):
            emoji_char = chr(record.emoji)
            if reply_message_id is None:
                self.database.mark_link_failed(record.id, 'missing reply for emoji reaction')
                return
            success, fallback = self.telegram_connection.send_reaction(
                chat_id=chat_id,
                message_id=reply_message_id,
                emoji=emoji_char,
            )
            if fallback:
                self.database.mark_link_sent(record.id, telegram_message_id=fallback.message_id)
            elif success:
                self.database.mark_link_sent(record.id)
            else:
                self.database.mark_link_retry(record.id, 'telegram reaction failed')
            return

        sender = record.sender or ''
        payload = record.payload or ''
        text = f"{sender}: {payload}" if sender else payload
        message = self.telegram_connection.send_message(
            chat_id=chat_id,
            text=text,
            reply_to_message_id=reply_message_id,
        )
        if message:
            self.database.mark_link_sent(record.id, telegram_message_id=message.message_id)
        else:
            self.database.mark_link_retry(record.id, 'telegram send returned None')

    def _forward_mesh_reaction(self, record, long_name: str, emoji_value: int, reply_id) -> None:
        """Forward a Meshtastic emoji reaction to Telegram."""

        if reply_id is None:
            self.database.mark_link_retry(record.id, 'emoji reaction missing reply target')
            return
        reply_record = self.database.get_link_by_meshtastic(reply_id)
        if not reply_record or not reply_record.telegram_message_id:
            self.logger.debug('No Telegram message mapped for reply %s', reply_id)
            self.database.mark_link_retry(record.id, 'missing Telegram message for reaction')
            return
        chat_id = self.config.enforce_type(int, self.config.Telegram.Room)
        emoji_char = chr(emoji_value)
        log_data = {
            "event": "mesh_to_telegram_reaction",
            "user": long_name,
            "emoji": emoji_value,
            "packet_id": record.meshtastic_packet_id,
            "reply_message_id": reply_record.telegram_message_id,
        }
        self.logger.info(json.dumps(log_data))
        success, fallback = self.telegram_connection.send_reaction(
            chat_id=chat_id,
            message_id=reply_record.telegram_message_id,
            emoji=emoji_char,
        )
        if fallback:
            self.database.mark_link_sent(record.id, telegram_message_id=fallback.message_id)
        elif success:
            self.database.mark_link_sent(record.id)
        else:
            self.database.mark_link_retry(record.id, 'telegram reaction failed')

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
        subscription_map = {
            "meshtastic.receive": self.on_receive,
            "meshtastic.connection.established": self.on_connection,
            "meshtastic.connection.lost": self.on_connection,
        }

        for topic, callback in subscription_map.items():
            pub.subscribe(callback, topic)

    # pylint:disable=too-many-locals
    def process_distance_command(self, packet, interface: meshtastic_serial_interface.SerialInterface) -> None:
        """
        Process /distance Meshtastic command

        :param packet:
        :param interface:
        :return:
        """
        from_id = str(packet.get('fromId', ''))
        mynode_info = interface.nodes.get(from_id)
        if not mynode_info:
            self.meshtastic_connection.send_text("distance err: no node info", destinationId=from_id)
            return
        position = mynode_info.get('position', {})
        if not position:
            self.meshtastic_connection.send_text("distance err: no position", destinationId=from_id)
            return
        my_latitude = position.get('latitude')
        my_longitude = position.get('longitude')
        if not (my_latitude and my_longitude):
            self.meshtastic_connection.send_text("distance err: no lat/lon", destinationId=from_id)
            return
        nodes_with_distance = []
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
            nodes_with_distance.append({'name': long_name, 'distance': distance})

        for node in sorted(nodes_with_distance, key=lambda x: x.get('distance', 0))[:10]:
            name = node.get('name')
            distance = humanize.intcomma(node.get('distance'))
            msg = f"{name}: {distance}m"
            self.meshtastic_connection.send_text(msg, destinationId=from_id)


    def process_ping_command(self, packet, _interface: meshtastic_serial_interface.SerialInterface) -> None:
        """
        Process /ping Meshtastic command

        :param packet:
        :param interface:
        :return:
        """
        from_id = str(packet.get('fromId', ''))
        self.ping_container[from_id] = {'timestamp': time.time()}
        payload = str.encode("test string")
        self.meshtastic_connection.send_data(payload,
                                             MESHTASTIC_BROADCAST_ADDR,
                                             # pylint:disable=no-member
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
        from_id = str(packet.get('fromId', ''))
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
        from_id = str(packet.get('fromId', ''))
        msg = decoded.get('text', '')
        if msg.startswith("/w"):
            self.process_weather_command(packet, interface)
            return
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


    @staticmethod
    def get_cur_temp(lat, lon, key):
        """
        get_cur_temp - get current weather using OpenWeatherMap
        """
        url = f"https://api.openweathermap.org/data/2.5/weather?appid={key}&units=metric&lat={lat}&lon={lon}"
        data = requests.get(url, timeout=10)
        dataj = data.json()
        short = f"T:{int(dataj.get('main').get('temp'))}C, P:{int(dataj.get('main').get('pressure'))}mb"
        short = f"{short}, H:{dataj.get('main').get('humidity')}%"
        short = f"{short}, W:{int(dataj.get('wind').get('speed'))}m/s"
        short = f"{short}, WD:{deg_to_cardinal(dataj.get('wind').get('deg'))}"
        short = f"{short}, C:{dataj.get('weather')[0].get('main')}"
        return short

    def process_weather_command(self, packet, interface):
        """
        Process /w (Weather) Meshtastic command)
        """
        from_id = str(packet.get('fromId', ''))
        found, _ = self.database.get_node_record(from_id)
        # not a new node
        if not found:
            self.meshtastic_connection.send_text("no information about your node available yet", destinationId=from_id)
            return
        lat, lon = self.meshtastic_connection.get_set_last_position(from_id)
        key = self.config.DEFAULT.OpenWeatherKey
        if len(key) == 0:
            self.meshtastic_connection.send_text("weather command disabled by configuration", destinationId=from_id)
            return
        try:
            text = self.get_cur_temp(lat, lon, key)
        except Exception as exc:  # pylint:disable=broad-exception-caught
            self.logger.error(repr(exc))
            text = "could not get weather, see bot logs"
        self.meshtastic_connection.send_text(text, destinationId=from_id)


    def process_uptime(self, packet, interface: meshtastic_serial_interface.SerialInterface) -> None:
        """
        Process /uptime Meshtastic command

        :param packet:
        :param interface:
        :return:
        """
        firmware = 'unknown'
        reboot_count = 'unknown'
        if interface.myInfo:
            firmware = interface.metadata.firmware_version
            reboot_count = interface.myInfo.reboot_count
        the_version = pkg_resources.get_distribution("meshtastic").version
        from_id = str(packet.get('fromId', ''))
        formatted_time = humanize.naturaltime(time.time() - self.meshtastic_connection.get_startup_ts)
        text = f'Bot v{VERSION}/FW: v{firmware}/Meshlib: v{the_version}/Reboots: {reboot_count}.'
        text += f'Started {formatted_time}'
        self.meshtastic_connection.send_text(text, destinationId=from_id)

    def process_pong(self, packet) -> None:
        """
        Process pong message

        :param packet:
        :return:
        """
        from_id = str(packet.get('fromId', ''))
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
        from_id = str(packet.get('fromId', ''))
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
            node_int = int(from_id.lstrip('!'), base=16)
            if ('%d' or '%s') in map_link:
                if '%d' in map_link:
                    map_link = map_link.replace('%d', str(node_int))
                if '%s' in map_link:
                    map_link = map_link.replace('%s', from_id)
                long_name = f"{long_name} {map_link}"
            else:
                # This is for built-in, though now obsolete map.
                # Please use https://meshmap.net/ or similar
                long_name = long_name.replace(' ', '%20')
                if '?tail=' in map_link:
                    long_name = f'{map_link}&name={long_name}'
                else:
                    long_name = f'{map_link}?name={long_name}'
        msg = f"{from_id} -> {long_name}"
        if self.config.enforce_type(bool, self.config.Meshtastic.WelcomeMessageEnabled):
            self.meshtastic_connection.send_text(self.config.Meshtastic.WelcomeMessage, destinationId=from_id)
        self.telegram_connection.send_message(chat_id=self.config.enforce_type(int,
                                                                               self.config.Telegram.NotificationsRoom),
                                              text=f"New node: {msg}")

    def _battery_emoji(self, level: int) -> str:
        """Return an emoji representing battery state."""
        if level is None:
            return "❓"
        if level >= 80:
            return "🟢"
        if level >= 50:
            return "🟡"
        if level >= 20:
            return "🟠"
        return "🔴"

    def notify_low_battery(
        self,
        node_id: str,
        battery: int,
        interface: meshtastic_serial_interface.SerialInterface,
        rx_time: float,
    ) -> None:
        """Send a Telegram message if battery level is below configured threshold."""
        if not self.config.enforce_type(bool, self.config.Meshtastic.LowBatteryAlertEnabled):
            return
        threshold = self.config.enforce_type(int, self.config.Meshtastic.LowBatteryThreshold)
        if battery is None:
            return
        # ignore outdated packets
        if rx_time < self.meshtastic_connection.get_startup_ts:
            return
        last_level = self.battery_cache.get(node_id)
        self.battery_cache[node_id] = battery
        if battery >= threshold or (last_level is not None and battery >= last_level):
            return
        node_name = node_id
        node_info = interface.nodes.get(node_id)
        if node_info is not None:
            user_info = node_info.get('user')
            node_name = user_info.get('longName', node_id)
        else:
            found, record = self.database.get_node_record(node_id)
            if found:
                node_name = record.nodeName
        emoji = self._battery_emoji(battery)
        self.telegram_connection.send_message(
            chat_id=self.config.enforce_type(int, self.config.Telegram.Room),
            text=f"Battery {emoji} {battery}% for {node_name}",
        )

    # pylint:disable=too-many-branches, too-many-statements, too-many-return-statements
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
        from_id = str(packet.get('fromId', ''))
        # from fix
        if from_id is None:
            from_id = hex(packet.get('from')).replace('0x', '')
            # pad nodes without a zero and prepend exclamation point
            from_id = f"!{from_id:>08}"
            packet['fromId'] = from_id
        # check for blacklist
        if self.filter.banned(from_id):
            self.logger.debug(f"User {from_id} is in a blacklist...")
            return
        # Send notifications if they're enabled
        if from_id is not None and self.config.enforce_type(bool, self.config.Telegram.NotificationsEnabled):
            self.notify_on_new_node(packet, interface)
        # check hop count
        hop_limit = packet.get('hopLimit', 0)
        if hop_limit > self.config.enforce_type(int, self.config.Meshtastic.MaxHopCount):
            self.logger.debug(f"User {from_id} exceeds {hop_limit}...")
            return
        #
        if decoded.get('portnum') != 'TEXT_MESSAGE_APP':
            # notifications
            if decoded.get('portnum') == 'POSITION_APP':
                # Log if writer is enabled
                if from_id is not None and self.config.enforce_type(bool, self.config.Meshtastic.NodeLogEnabled):
                    self.writer.write(packet)
                self.database.store_location(packet)

                # Low battery alert from position updates
                battery = decoded.get('position', {}).get('batteryLevel')
                self.notify_low_battery(from_id, battery, interface, packet.get('rxTime', 0))

                # Send Meshtastic node coordinates to APRS for licenced operators
                if self.aprs is not None and from_id is not None:
                    self.aprs.send_location(packet)
                return
            # pong
            if decoded.get('portnum') == 'REPLY_APP':
                self.process_pong(packet)
                return
            if decoded.get('portnum') == 'TELEMETRY_APP':
                battery = decoded.get('telemetry', {}).get('deviceMetrics', {}).get('batteryLevel')
                self.notify_low_battery(from_id, battery, interface, packet.get('rxTime', 0))
                return
            return
        # get msg
        msg = decoded.get('text', '')

        # ignore non-broadcast messages
        if to_id != MESHTASTIC_BROADCAST_ADDR:
            if msg.startswith('/'):
                self.process_meshtastic_command(packet, interface)
                return

            text = self.bot_handler.get_response(from_id, msg)
            if text:
                self.logger.info(f"{from_id}: {msg} -> {text}")
                self.meshtastic_connection.send_text(text, destinationId=from_id)

            return
        # Save messages
        try:
            self.database.store_message(packet)
        except Exception as exc:  # pylint:disable=broad-except
            self.logger.error('Could not store message: ', exc, repr(exc))
        # Process commands and forward messages
        node_info = interface.nodes.get(from_id)
        long_name = from_id
        if node_info is not None:
            user_info = node_info.get('user')
            long_name = user_info.get('longName')
        else:  # get from DB
            found, record = self.database.get_node_record(from_id)
            if found:
                long_name = record.nodeName
        # skip commands
        if msg.startswith('/'):
            self.process_meshtastic_command(packet, interface)
            return

        # Range test module should not spam telegram room
        if re.match(r'^seq\s[0-9]+', msg, re.I) is not None:
            self.logger.debug(f"User {long_name} has sent range test... {msg}")
            return

        # Telemetry
        node_part = from_id[5:]
        if re.match(r'^(\-?[0-9]+,)+' + f'{node_part}$', msg) is not None:
            self.logger.debug('Banned telemetry: ', from_id, msg)
            return

        # Meshtastic nodes sometimes duplicate messages sent by bot. Filter these.
        self_name = self.meshtastic_connection.interface.getLongName()
        if msg.startswith(self_name) or self_name == long_name:
            self.logger.debug(f"Bot duplicate via meshtastic... {msg}")
            return

        long_name = long_name.strip()
        # Do cache check
        key = f"{long_name}:{msg}"
        if msg and self.memcache.get_ex(key):
            self.logger.debug(f"Cache hit for {key}")
            return
        if msg:
            self.memcache.set(key, True, expires=300)
        packet_id = packet.get('id')
        reply_id = decoded.get('replyId') or decoded.get('reply_id')
        try:
            reply_id = int(reply_id) if reply_id is not None else None
        except (TypeError, ValueError):
            reply_id = None
        emoji_value = decoded.get('emoji')
        try:
            emoji_value = int(emoji_value) if emoji_value is not None else None
        except (TypeError, ValueError):
            emoji_value = None
        record = self.database.ensure_message_link(
            direction=MESSAGE_DIRECTION_MESH_TO_TELEGRAM,
            meshtastic_packet_id=packet_id,
            payload=msg,
            sender=long_name,
            reply_to_packet_id=reply_id,
            emoji=emoji_value,
        )

        if emoji_value is not None and (msg is None or msg == ''):
            self._forward_mesh_reaction(record, long_name, emoji_value, reply_id)
            return

        reply_message_id = None
        if reply_id is not None:
            reply_record = self.database.get_link_by_meshtastic(reply_id)
            if reply_record and reply_record.telegram_message_id:
                reply_message_id = reply_record.telegram_message_id

        log_data = {
            "event": "mesh_to_telegram",
            "user": long_name,
            "message": msg,
            "packet_id": packet_id,
            "reply_id": reply_id,
            "emoji": emoji_value,
        }
        self.logger.info(json.dumps(log_data))

        if msg.startswith('APRS-'):
            addressee = msg.split(' ')[0].lstrip('APRS-').rstrip(':')
            new_msg = msg.replace(msg.split(' ')[0], '').strip()
            self.aprs.send_text(addressee, f'{long_name}: {new_msg}')

        message = self.telegram_connection.send_message(
            chat_id=self.config.enforce_type(int, self.config.Telegram.Room),
            text=f"{long_name}: {msg}",
            reply_to_message_id=reply_message_id,
        )
        if message:
            self.database.mark_link_sent(record.id, telegram_message_id=message.message_id)
        else:
            self.database.mark_link_retry(record.id, 'telegram send returned None')

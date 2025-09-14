# -*- coding: utf-8 -*-
""" APRS connection module """

import logging
import re
from typing import Any, Dict, List, Optional, Tuple
#
from datetime import datetime
from decimal import Decimal
from threading import Thread
#
import aprslib
#
from pubsub import pub
# pylint:disable=no-name-in-module
from setproctitle import setthreadtitle
#
from mtg.config import Config
from mtg.filter import CallSignFilter
from mtg.utils import Memcache
from mtg.utils.rf.prefixes import ITUPrefix

class APRSStreamer:  # pylint:disable=too-many-instance-attributes
    """
    APRS streamer
    """

    def __init__(self, config: Config, itu_prefix: ITUPrefix):
        self.aprs_is = None
        self.filter: Optional[CallSignFilter] = None
        self.config = config
        self.logger: Optional[logging.Logger] = None
        self.exit = False
        self.name = 'APRS Streamer'
        self.database = None
        self.connection = None
        self.telegram_connection = None
        self.memcache = Memcache(self.logger)
        self.itu_prefix = itu_prefix
        # preload these on start
        self.prefixes: List[str] = []

    def set_telegram_connection(self, telegram_connection: Any) -> None:
        """
        Set telegram connection
        """
        self.telegram_connection = telegram_connection

    def set_db(self, database: Any) -> None:
        """
        Set database
        """
        self.database = database

    def set_logger(self, logger: logging.Logger) -> None:
        """
        Set class logger

        :param logger:
        :return:
        """
        self.logger = logger

    def set_meshtastic(self, connection: Any) -> None:
        """
        set_meshtastic - set meshtastic connection

        :param connection:
        :return:
        """
        self.connection = connection

    def set_filter(self, filter_class: CallSignFilter) -> None:
        """
        Set APRS callsign filter class

        :param filter_class:
        :return:
        """
        self.filter = filter_class

    def send_packet(self, packet: str) -> None:
        """
        Send APRS packet

        :param packet:
        :return:
        """
        if not self.config.enforce_type(bool, self.config.APRS.FromMeshtastic):
            return
        if self.aprs_is is not None:
            self.aprs_is.sendall(packet)

    def send_text(self, addressee: str, message: str) -> None:
        """
        Send APRS text message
        """
        packet = f'{self.config.APRS.Callsign}>APDR15,WIDE1-1,WIDE2-2::{addressee:9}:{message}'
        self.send_packet(packet)

    def process(self, packet: Dict[str, Any]) -> None:
        """
        Process APRS packet

        :param packet:
        :return:
        """
        if not self.config.enforce_type(bool, self.config.APRS.ToMeshtastic):
            return
        if packet.get('format') != 'message' or not packet.get('message_text', ''):
            return
        if packet.get('addresse') != self.config.APRS.Callsign:
            return
        if self.logger is not None:
            self.logger.info(f'Got APRS PACKET: {packet}')
        msg = packet.get('message_text')
        node = packet.get('from')
        msg_no = str(packet.get('msgNo', ''))
        if msg_no:
            self.send_text(str(node) if node is not None else '', 'ack' + str(msg_no))
        if msg is not None and node is not None and self.memcache.get(str(node) + str(msg)):
            return
        # bot functionality
        if msg is not None and msg.lower() in ['ping', 'test']:
            if node is not None:
                self.send_text(str(node), 'passed')
        #
        if node is not None and msg is not None:
            self.memcache.set(str(node) + str(msg), True, expires=300)
        # TG
        if self.telegram_connection is not None and node is not None and msg is not None:
            self.telegram_connection.send_message_sync(
                chat_id=self.config.enforce_type(int, self.config.Telegram.NotificationsRoom),
                text=f"APRS-{str(node)}: {str(msg)}"
            )
        # Mesh
        if self.connection is not None and node is not None and msg is not None:
            self.connection.send_text(f"APRS-{str(node)}: {str(msg)}")
        return

    @staticmethod
    def callback(packet: Dict[str, Any]) -> None:
        """
        APRS packet callback

        :param packet:
        :return:
        """
        pub.sendMessage('APRS', packet=packet)

    @staticmethod
    def get_imag(value: float) -> float:
        """
        Get imaginary part of float
        """
        return float((Decimal(str(value)) - (Decimal(str(value)) // 1)))

    def dec2sexagesimal(self, value: float) -> Tuple[int, int, int]:
        """
        Convert decimal to sexagesimal
        """
        by60 = float(Decimal(str(self.get_imag(value))) * 60)
        remainder = int(self.get_imag(by60) * 60)
        return int(value), int(by60), remainder

    def send_location(self, packet: Dict[str, Any]) -> None:  # pylint:disable=too-many-locals,too-many-branches
        """
        Send location to APRS
        """
        from_id = packet.get("fromId")
        if not from_id:
            return
        try:
            if self.database is not None:
                node_record = self.database.get_node_info(from_id)
            else:
                raise RuntimeError("Database not available")
        except RuntimeError:
            if self.logger is not None:
                self.logger.warning('Node %s not in node DB', from_id)
            return
        # cache node position for 60 seconds
        key = f"{from_id}-location"
        if self.memcache.get(key):
            return
        self.memcache.set(key, True, expires=60)
        #
        position = packet.get('decoded', {}).get('position', {})
        altitude=int(position.get('altitude', 0) * 3.28084)
        latitude=position.get('latitude', 0)
        longitude=position.get('longitude', 0)
        # get node info
        node_name = re.sub('[^A-Za-z0-9-]+', '', node_record.nodeName if node_record else '')
        if len(node_name) == 0:
            return
        #
        found = False
        for prefix in self.prefixes:
            full_reg = f'^{prefix}' + '[0-9][A-Z]{2,3}(-[0-9]{1,2})?$'
            if re.match(full_reg, node_name, flags=re.I):
                found = True
                break
        #
        if not found:
            if self.logger is not None:
                self.logger.warning('APRS: %s not a ham call sign', node_name)
            return
        #
        degrees, minutes, seconds = self.dec2sexagesimal(latitude)
        pad_sec = f'{abs(seconds):<02d}'
        letter = 'S' if latitude < 0 else 'N'
        latitude_packet = f'{abs(degrees)}{abs(minutes)}.{pad_sec}{letter}'
        degrees, minutes, seconds = self.dec2sexagesimal(longitude)
        pad_v = f'{abs(degrees)}{abs(minutes)}'
        pad_d = f'{pad_v:>05}'
        pad_sec = f'{abs(seconds):<02d}'
        letter = 'W' if longitude < 0 else 'E'
        longitude_packet = f'{pad_d}.{pad_sec}{letter}'
        coordinates = f'{latitude_packet}/{longitude_packet}'
        #
        timestamp = datetime.now().strftime("%d%H%M")
        room_link = self.config.Telegram.RoomLink
        # Consistensy for callsigns
        node_name = node_name.upper()
        aprs_packet = f"{node_name}>APRS,TCPIP*:@{timestamp}/{coordinates}-/A={altitude:06d} Forwarded for {room_link}"
        if self.aprs_is is not None:
            self.aprs_is.sendall(aprs_packet)
        if self.logger is not None:
            self.logger.warning('APRS: %s', aprs_packet)

    def run_loop(self) -> None:
        """
        APRS streamer loop

        :return:
        """
        setthreadtitle(self.name)
        country = self.itu_prefix.get_country_by_callsign(self.config.APRS.Callsign)
        if not country:
            raise RuntimeError(f'Could not get country for callsign {self.config.APRS.Callsign}')
        # preload prefixes
        prefixes = self.itu_prefix.get_prefixes_by_callsign(self.config.APRS.Callsign)
        self.prefixes = prefixes if prefixes is not None else []
        #
        if self.logger is not None:
            self.logger.info(f'Starting APRS for country {country}...')
        self.aprs_is = aprslib.IS(self.config.APRS.Callsign,
                                  self.config.APRS.Password,
                                  host='rotate.aprs2.net',
                                  port=14580)
        f_filter = f"r/{self.config.enforce_type(float, self.config.WebApp.Center_Latitude)}/"
        f_filter += f"{self.config.enforce_type(float, self.config.WebApp.Center_Longitude)}/50"
        if self.aprs_is is not None:
            self.aprs_is.set_filter(f_filter)
        #
        while not self.exit:
            try:
                if self.aprs_is is not None:
                    self.aprs_is.connect()
                    self.aprs_is.consumer(self.callback, immortal=True)
            except KeyboardInterrupt:
                break
            except aprslib.exceptions.ConnectionDrop:
                if self.logger is not None:
                    self.logger.debug("aprs conn drop")
            except aprslib.exceptions.LoginError:
                if self.logger is not None:
                    self.logger.debug("aprs login error")

    def shutdown(self) -> None:
        """
        Shutdown APRS streamer
        """
        self.exit = True

    def run(self) -> None:
        """
        APRS runner

        :return:
        """
        if self.config.enforce_type(bool, self.config.APRS.Enabled):
            pub.subscribe(self.process, 'APRS')
            thread = Thread(target=self.run_loop, daemon=True, name=self.name)
            thread.start()

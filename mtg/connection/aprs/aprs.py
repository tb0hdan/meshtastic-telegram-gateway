# -*- coding: utf-8 -*-
""" APRS connection module """

import logging
import re
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

class APRSStreamer:  # pylint:disable=too-many-instance-attributes
    """
    APRS streamer
    """

    def __init__(self, config: Config):
        self.aprs_is = None
        self.filter = None
        self.config = config
        self.logger = None
        self.exit = False
        self.name = 'APRS Streamer'
        self.database = None
        self.connection = None
        self.telegram_connection = None
        self.memcache = Memcache(self.logger)

    def set_telegram_connection(self, telegram_connection):
        """
        Set telegram connection
        """
        self.telegram_connection = telegram_connection

    def set_db(self, database):
        """
        Set database
        """
        self.database = database

    def set_logger(self, logger: logging.Logger):
        """
        Set class logger

        :param logger:
        :return:
        """
        self.logger = logger

    def set_meshtastic(self, connection) -> None:
        """
        set_meshtastic - set meshtastic connection

        :param connection:
        :return:
        """
        self.connection = connection

    def set_filter(self, filter_class: CallSignFilter):
        """
        Set APRS callsign filter class

        :param filter_class:
        :return:
        """
        self.filter = filter_class

    def send_packet(self, packet):
        """
        Send APRS packet

        :param packet:
        :return:
        """
        if not self.config.enforce_type(bool, self.config.APRS.FromMeshtastic):
            return
        self.aprs_is.sendall(packet)

    def send_text(self, addressee, message):
        """
        Send APRS text message
        """
        packet = f'{self.config.APRS.Callsign}>APDR15,WIDE1-1,WIDE2-2::{addressee:9}:{message}'
        self.send_packet(packet)

    def process(self, packet):
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
        self.logger.info(f'Got APRS PACKET: {packet}')
        msg = packet.get('message_text')
        node = packet.get('from')
        msg_no = str(packet.get('msgNo', ''))
        if msg_no:
            self.send_text(node, 'ack' + msg_no)
        if self.memcache.get(node + msg):
            return
        # bot functionality
        if msg.lower() in ['ping', 'test']:
            self.send_text(node, 'passed')
        #
        self.memcache.set(node + msg, True, expires=300)
        # TG
        self.telegram_connection.send_message(chat_id=self.config.enforce_type(int,
                                                                               self.config.Telegram.NotificationsRoom),
                                              text=f"APRS-{node}: {msg}")
        # Mesh
        self.connection.send_text(f"APRS-{node}: {msg}")
        return

    @staticmethod
    def callback(packet):
        """
        APRS packet callback

        :param packet:
        :return:
        """
        pub.sendMessage('APRS', packet=packet)

    @staticmethod
    def get_imag(value):
        """
        Get imaginary part of float
        """
        return float((Decimal(str(value)) - (Decimal(str(value)) // 1)))

    def dec2sexagesimal(self, value):
        """
        Convert decimal to sexagesimal
        """
        by60 = float(Decimal(str(self.get_imag(value))) * 60)
        remainder = int(self.get_imag(by60) * 60)
        return int(value), int(by60), remainder

    def send_location(self, packet):  # pylint:disable=too-many-locals
        """
        Send location to APRS
        """
        from_id = packet.get("fromId")
        if not from_id:
            return
        node_record = self.database.get_node_info(from_id)
        position = packet.get('decoded', {}).get('position', {})
        altitude=int(position.get('altitude', 0) * 3.28084)
        latitude=position.get('latitude', 0)
        longitude=position.get('longitude', 0)
        # get node info
        node_name = re.sub('[^A-Za-z0-9-]+', '', node_record.nodeName)
        if len(node_name) == 0:
            return
        # Support other countries
        if not re.match('^U[R-Z][0-9][A-Z]{2,3}(-[0-9]{1,2})?$', node_name, flags=re.I):
            self.logger.warning('APRS: %s not a ham call-sign', node_name)
            return
        degrees, minutes, seconds = self.dec2sexagesimal(latitude)
        pad_sec = f'{seconds:<02d}'
        letter = 'S' if latitude < 0 else 'N'
        latitude_packet = f'{abs(degrees)}{minutes}.{pad_sec}{letter}'
        degrees, minutes, seconds = self.dec2sexagesimal(longitude)
        pad_v = f'{abs(degrees)}{minutes}'
        pad_d = f'{pad_v:>05}'
        pad_sec = f'{seconds:<02d}'
        letter = 'W' if longitude < 0 else 'E'
        longitude_packet = f'{pad_d}.{pad_sec}{letter}'
        coordinates = f'{latitude_packet}/{longitude_packet}'
        #
        timestamp = datetime.now().strftime("%d%H%M")
        room_link = self.config.Telegram.RoomLink
        aprs_packet = f"{node_name}>APRS,TCPIP*:@{timestamp}/{coordinates}-/A={altitude:06d} Forwarded for {room_link}"
        self.aprs_is.sendall(aprs_packet)
        self.logger.warning('APRS: %s', aprs_packet)

    def run_loop(self):
        """
        APRS streamer loop

        :return:
        """
        setthreadtitle(self.name)
        self.aprs_is = aprslib.IS(self.config.APRS.Callsign,
                                  self.config.APRS.Password,
                                  host='euro.aprs2.net',
                                  port=14580)
        f_filter = f"r/{self.config.enforce_type(float, self.config.WebApp.Center_Latitude)}/"
        f_filter += f"{self.config.enforce_type(float, self.config.WebApp.Center_Longitude)}/50"
        self.aprs_is.set_filter(f_filter)
        #
        while not self.exit:
            try:
                self.aprs_is.connect()
                self.aprs_is.consumer(self.callback, immortal=True)
            except KeyboardInterrupt:
                break
            except aprslib.exceptions.ConnectionDrop:
                self.logger.debug("aprs conn drop")
            except aprslib.exceptions.LoginError:
                self.logger.debug("aprs login error")

    def shutdown(self):
        """
        Shutdown APRS streamer
        """
        self.exit = True

    def run(self):
        """
        APRS runner

        :return:
        """
        if self.config.enforce_type(bool, self.config.APRS.Enabled):
            pub.subscribe(self.process, 'APRS')
            thread = Thread(target=self.run_loop, daemon=True, name=self.name)
            thread.start()

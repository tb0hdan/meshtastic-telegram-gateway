import logging
#
from threading import Thread
#
import aprslib
#
from pubsub import pub
#
from mtg.config import Config
from mtg.filter import CallSignFilter

class APRSStreamer:
    """
    APRS streamer
    """
    def __init__(self, config: Config):
        self.aprs_is = None
        self.filter = None
        self.config = config
        self.logger = None
        self.exit = False

    def set_logger(self, logger: logging.Logger):
        """
        Set class logger

        :param logger:
        :return:
        """
        self.logger = logger

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

    def process(self, packet):
        """
        Process APRS packet

        :param packet:
        :return:
        """
        if not self.config.enforce_type(bool, self.config.APRS.ToMeshtastic):
            return
        self.logger.debug(packet)

    @staticmethod
    def callback(packet):
        """
        APRS packet callback

        :param packet:
        :return:
        """
        pub.sendMessage('APRS', packet=packet)

    def run_loop(self):
        """
        APRS streamer loop

        :return:
        """
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

    def run(self):
        """
        APRS runner

        :return:
        """
        if self.config.enforce_type(bool, self.config.APRS.Enabled):
            pub.subscribe(self.process, 'APRS')
            thread = Thread(target=self.run_loop, daemon=True)
            thread.start()

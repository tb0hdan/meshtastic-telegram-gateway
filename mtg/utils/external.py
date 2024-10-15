# pylint: disable=duplicate-code
#-*- coding: utf-8 -*-
""" External plugin base class """

from threading import Thread

from .imp import list_classes


class ExternalPlugins:
    """
    ExternalPlugins - container for user supplied plugins
    """
    # pylint:disable=too-many-arguments,too-many-positional-arguments
    def __init__(self, database, config, meshtastic_connection, telegram_connection, logger):
        self.database = database
        self.config = config
        self.meshtastic_connection = meshtastic_connection
        self.telegram_connection = telegram_connection
        self.logger = logger

    def run(self):
        """
        run - start external plugins, each inside separate thread
        """
        for cls in list_classes(self.logger, package='external', base_class='ExternalBase'):
            clsobj = cls(self.database, self.config, self.meshtastic_connection, self.telegram_connection, self.logger)
            t = Thread(target=clsobj.run)
            t.start()

        for cls in list_classes(self.logger, package='external', base_class='ExternalBaseMesh'):
            clsobj = cls(self.database, self.config, self.meshtastic_connection, self.telegram_connection, self.logger)
            t = Thread(target=clsobj.run)
            t.start()

        for cls in list_classes(self.logger, package='external', base_class='ExternalBaseTG'):
            clsobj = cls(self.database, self.config, self.meshtastic_connection, self.telegram_connection, self.logger)
            t = Thread(target=clsobj.run)
            t.start()

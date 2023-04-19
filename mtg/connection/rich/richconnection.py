# -*- coding: utf-8 -*-
""" Rich Meshtastic connection. Original one fused with DB features """

import logging
import random
import time
from typing import List

from mtg.database import MeshtasticDB
from mtg.connection.meshtastic import MeshtasticConnection


class RichConnection(MeshtasticConnection):
    """
    RichConnection - enriched Meshtastic connection
    """

    # pylint:disable=too-many-arguments
    def __init__(self, dev_path: str, logger: logging.Logger, config, filter_class,
                 database: MeshtasticDB, startup_ts=time.time(), rg_fn=None):
        super().__init__(dev_path, logger, config, filter_class, startup_ts)
        self.config = config
        self.database = database
        self.logger = logger
        random.seed()
        self.rg_fn = rg_fn

    def get_set_last_position(self, node_id):
        """
        Get last position from DB or generate random one

        :param node_id:
        :return:
        """
        lat_r = self.config.enforce_type(float,
                                         self.config.WebApp.Center_Latitude) + random.randrange(1000) / 10000
        lon_r = self.config.enforce_type(float,
                                         self.config.WebApp.Center_Longitude) + random.randrange(1000) / 10000
        lat, lon = 0.0, 0.0
        try:
            lat, lon = self.database.get_last_coordinates(node_id)
        except RuntimeError:
            # no coordinates in DB
            self.database.set_coordinates(node_id, lat_r, lon_r)
        lat = lat or lat_r
        lon = lon or lon_r
        return lat, lon

    @property
    def nodes_with_position(self) -> List:
        """
        Filter out nodes without position
        'position': {'latitudeI': 464305648, 'longitudeI': 306971256, 'altitude': 107,
                     'latitude': 46.4305648, 'longitude': 30.6971256}

        :return:
        """
        node_list = []
        for node_info in self.nodes_with_info:
            node_id = node_info.get('user', {}).get('id')
            position = node_info.get('position', {})
            if not (position.get('latitude') and position.get('longitude')):
                self.logger.debug(f"Node {node_id} doesn't have position...")
                lat, lon = self.get_set_last_position(node_id)
                latitude_i = str(lat).replace('.', '')[:9]
                longitude_i = str(lon).replace('.', '')[:9]
                node_info['position'] = {'latitude': lat, 'longitude': lon,
                                         'latitudeI': latitude_i, 'longitudeI': longitude_i,
                                         'altitude': 100}
            if rg_results := self.rg_fn(
                (
                    node_info['position']['latitude'],
                    node_info['position']['longitude'],
                )
            ):
                node_info['position']['admin1'] = rg_results[0]['admin1']
            node_list.append(node_info)
        return node_list

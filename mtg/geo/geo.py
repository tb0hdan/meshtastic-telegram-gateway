# -*- coding: utf-8 -*-
""" Geographical utilities module """

import haversine


def get_lat_lon_distance(latlon1: tuple, latlon2: tuple) -> float:
    """
    Get distance (in meters) between two geographical points using GPS coordinates

    :param latlon1:
    :param latlon2:
    :return:
    """
    if not isinstance(latlon1, tuple):
        raise RuntimeError('Tuple expected for latlon1')
    if not isinstance(latlon2, tuple):
        raise RuntimeError('Tuple expected for latlon2')
    return haversine.haversine(latlon1, latlon2, unit=haversine.Unit.METERS)

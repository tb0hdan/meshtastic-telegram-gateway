# pylint: skip-file
#-*- coding: utf-8 -*-
""" Geo utils """

def deg_to_cardinal(deg):
    """
    deg_to_cardinal - convert degrees to cardinal directions
    """
    if deg > 348.75 and deg <= 360:
        return "N"
    if deg >= 0 and deg <= 11.25:
        return "N"
    if deg > 11.25 and deg <= 33.75:
        return "NNE"
    if deg > 33.75 and deg <= 56.25:
        return "NE"
    if deg > 56.25 and deg <= 78.75:
        return "ENE"
    if deg > 78.75 and deg <= 101.25:
        return "E"
    if deg > 101.25 and deg <= 123.75:
        return "ESE"
    if deg > 123.75 and deg <= 146.25:
        return "SE"
    if deg > 146.25 and deg <= 168.75:
        return "SSE"
    if deg > 168.75 and deg <= 191.25:
        return "S"
    if deg > 191.25 and deg <= 213.75:
        return "SSW"
    if deg > 213.75 and deg <= 236.25:
        return "SW"
    if deg > 236.25 and deg <= 258.75:
        return "WSW"
    if deg > 258.75 and deg <= 281.25:
        return "W"
    if deg > 281.25 and deg <= 303.75:
        return "WNW"
    if deg > 303.75 and deg <= 326.25:
        return "NW"
    if deg > 326.25 and deg <= 348.75:
        return "NNW"
    return "UNK"

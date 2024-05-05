# -*- coding: utf-8 -*-
""" HAM Prefixes utilities """

from . import ITUPrefix

class France(ITUPrefix):
    """
    Country class - France
    """
    # https://en.wikipedia.org/wiki/ITU_prefix
    PREFIXES = ['F', 'HW', 'HX', 'HY', 'TH', 'TK', 'TM', 'TO', 'TP', 'TQ',
            'TV', 'TW', 'TX'
    ]

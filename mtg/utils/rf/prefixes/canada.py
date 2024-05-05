# -*- coding: utf-8 -*-
""" HAM Prefixes utilities """

from . import ITUPrefix

class Canada(ITUPrefix):
    """
    Country class - Canada
    """
    # https://en.wikipedia.org/wiki/ITU_prefix
    PREFIXES = ['CB', 'CF', 'CG', 'CH', 'CI', 'CJ', 'CK', 'CY', 'CZ',
            'VA', 'VB', 'VC', 'VD', 'VE', 'VF', 'VG', 'VO',
            'VX', 'VY',
            'XJ', 'XK', 'XL', 'XM', 'XN', 'XO'
    ]

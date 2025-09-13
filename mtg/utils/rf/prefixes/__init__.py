# -*- coding: utf-8 -*-
""" HAM Prefixes utilities """

from typing import Any, Dict, List, Optional, Type
from mtg.utils import list_classes

class ITUPrefix:
    """
    ITUPrefix: HAM Radio prefixes class
    """
    def __init__(self, logger: Any) -> None:
        self.logger = logger

    def get_classes(self) -> List[Type[Any]]:
        """
        get_classes - get prefix classes
        """
        return list_classes(self.logger, package='mtg.utils.rf.prefixes', base_class=type(self).__name__)

    def get_prefixes(self) -> Dict[str, List[str]]:
        """
        get_prefixes - get prefixes
        """
        prefixes = {}
        for cls in self.get_classes():
            name = type(cls(self.logger)).__name__
            if len(cls.PREFIXES) == 0:
                raise RuntimeError(f"Class {name} doesn't have prefixes assigned")
            prefixes[name] = cls.PREFIXES
        return prefixes

    def get_country_by_callsign(self, callsign: str) -> Optional[str]:
        """
        get_country_by_callsign - get country by call sign
        """
        countries = self.get_prefixes()
        if len(countries) == 0:
            return None
        for name, prefixes in countries.items():
            for prefix in prefixes:
                if callsign.upper().startswith(prefix):
                    return name
        return None

    def get_prefixes_by_callsign(self, callsign: str) -> Optional[List[str]]:
        """
        get_prefixes_by_callsign - get prefixes by call sign
        """
        countries = self.get_prefixes()
        if len(countries) == 0:
            return None
        for _, prefixes in countries.items():
            for prefix in prefixes:
                if callsign.upper().startswith(prefix):
                    return prefixes
        return None

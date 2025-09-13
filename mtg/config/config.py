# -*- coding: utf-8 -*-
""" Configuration module """

import configparser
from typing import Any, List, Optional, Type, Union


class Config:
    """
    Config - two level configuration with functionality similar to dotted dict
    """

    def __init__(self, config_path: str = "mesh.ini") -> None:
        self.config_path: str = config_path
        self.config: Optional[configparser.ConfigParser] = None
        self.elements: List[str] = []

    def read(self) -> None:
        """
        Read configuration file

        :return:
        """
        self.config = configparser.ConfigParser()
        self.config.read(self.config_path)

    @staticmethod
    def enforce_type(value_type: Type[Union[bool, int, float, str]], value: str) -> Union[bool, int, float, str]:
        """
        Enforce selected type

        :param value_type:
        :param value:
        :return:
        """
        return value.lower() == 'true' if value_type == bool else value_type(value)

    def __getattr__(self, attr: str) -> Any:
        """
        Get attribute

        :param attr:
        :return:
        """
        if self.config is None:
            raise AttributeError('config is empty')
        if len(self.elements) < 2:
            self.elements.append(attr)
        if len(self.elements) == 2:
            result = self.config[self.elements[0]][self.elements[1]]
            self.elements = []
            return result
        return self

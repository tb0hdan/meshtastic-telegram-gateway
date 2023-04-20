# -*- coding: utf-8 -*-
""" Configuration module """

import configparser


class Config:
    """
    Config - two level configuration with functionality similar to dotted dict
    """

    def __init__(self, config_path="mesh.ini"):
        self.config_path = config_path
        self.config = None
        self.elements = []

    def read(self):
        """
        Read configuration file

        :return:
        """
        self.config = configparser.ConfigParser()
        self.config.read(self.config_path)

    @staticmethod
    def enforce_type(value_type, value):
        """
        Enforce selected type

        :param value_type:
        :param value:
        :return:
        """
        return value.lower() == 'true' if value_type == bool else value_type(value)

    def __getattr__(self, attr):
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

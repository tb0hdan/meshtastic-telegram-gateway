#!/usr/bin/env python3
# -*- coding: utf-8 -*-
""" Meshtastic Telegram Gateway """

import os
from mtg import cmd

if __name__ == '__main__':
    basedir = os.path.abspath(os.path.dirname(__file__))
    cmd(basedir)

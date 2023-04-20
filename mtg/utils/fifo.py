# -*- coding: utf-8 -*-
""" FIFO module """

import errno
import os


def create_fifo(path):
    """
    Create FIFO

    :param path:
    :return:
    """
    try:
        os.mkfifo(path)
    except OSError as exc:
        if exc.errno != errno.EEXIST:
            raise

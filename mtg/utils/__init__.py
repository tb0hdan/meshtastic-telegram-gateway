# -*- coding: utf-8 -*-
""" Utilities module """

from .exc import log_exception
from .fifo import create_fifo
from .imp import list_classes
from .memcache import Memcache
from .message import (
    split_message,
    split_user_message,
    is_emoji_reaction,
    first_emoji_codepoint,
)
from .external import ExternalPlugins

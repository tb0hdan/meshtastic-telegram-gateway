# -*- coding: utf-8 -*-
"""Global pytest configuration and fixtures to avoid import conflicts"""

import sys
from unittest.mock import MagicMock

# Mock external dependencies before any imports happen
external_modules = [
    'telegram',
    'telegram.ext',
    'telegram.constants',
    'meshtastic',
    'meshtastic.serial_interface',
    'meshtastic.tcp_interface',
    'meshtastic.mesh_pb2',
    'meshtastic.portnums_pb2',
    'meshtastic.stream_interface',
    'slack_sdk',
    'slack_sdk.rtm_v2',
    'setproctitle',
    'pubsub',
    'pubsub.pub',
    'requests',
    'pyqrcode',
    'humanize',
    'paho',
    'paho.mqtt',
    'paho.mqtt.client',
]

for module in external_modules:
    if module not in sys.modules:
        sys.modules[module] = MagicMock()

# Mock specific attributes that are commonly used
sys.modules['meshtastic'].BROADCAST_ADDR = "^all"
sys.modules['meshtastic'].LOCAL_ADDR = "!local"

# Mock telegram Update class
sys.modules['telegram'].Update = MagicMock()
sys.modules['telegram'].Update.ALL_TYPES = "all_types"

# Mock mesh_pb2 constants
mock_constants = MagicMock()
mock_constants.DATA_PAYLOAD_LEN = 240
sys.modules['meshtastic'].mesh_pb2 = MagicMock()
sys.modules['meshtastic'].mesh_pb2.Constants = mock_constants
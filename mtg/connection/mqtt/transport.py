#-*- coding: utf-8 -*-
""" MQTT to Radio emulation transport module """

import base64
import json
import struct
import time
from threading import Thread

from cryptography.hazmat.primitives.ciphers import (
    Cipher, algorithms, modes
)


from meshtastic.stream_interface import StreamInterface
from meshtastic import mqtt_pb2, mesh_pb2, BROADCAST_NUM, BROADCAST_ADDR
from meshtastic import portnums_pb2 as PortNum

import paho.mqtt.client as mqtt
from google.protobuf import json_format

from getmac import get_mac_address as gma

from .common import CommonMQTT

class MQTTCrypto:
    """ MQTT Crypto module """
    KEY = 'd4f1bb3a20290759f0bcffabcf4e6901'
    def __init__(self, key=None):
        self.key = bytes.fromhex(key) if key else bytes.fromhex(self.KEY)

    @staticmethod
    def init_nonce(from_node, packet_id):
        """
        init_nonce - Initialize nonce. Ported from meshtastic/firmware
        """
        nonce = bytearray(16)
        nonce[:8] = struct.pack('<Q', packet_id)
        nonce[8:12] = struct.pack('<I', from_node)
        return nonce

    @staticmethod
    def decrypt(key, nonce, ciphertext):
        """
        decrypt - decrypt data using nonce and ciphertext
        """
        decryptor = Cipher(
            algorithms.AES(key),
            modes.CTR(nonce),
        ).decryptor()

        return decryptor.update(ciphertext) + decryptor.finalize()

    def decrypt_packet(self, packet):
        """
        decrypt_packet - decrypt MQTT packet
        """
        data = base64.b64decode(packet.get('encrypted'))
        nonce = self.init_nonce(packet.get('from'), packet.get('id'))
        r = self.decrypt(self.key, nonce, data)
        return mesh_pb2.Data().FromString(r)  # pylint:disable=no-member

    def encrypt_packet(self):
        """
        encrypt_packet - Not implemented yet
        """
        return


class MQTTInterface(StreamInterface):  # pylint:disable=too-many-instance-attributes
    """
    MQTTInterface - MQTT to Radio emulation transport class
    """
    def __init__(self, debugOut=None,  # pylint:disable=too-many-arguments
                 noProto=False,
                 connectNow=True,
                 cfg=None,
                 logger=None):

        self.stream = None
        self.cfg = cfg
        self.logger = logger
        self.connection_thread = None
        self.name = "MQTT Interface"
        #
        self.topic = (
            self.cfg.MQTT.Topic
            if self.cfg.MQTT.Topic.endswith('#')
            else f'{self.cfg.MQTT.Topic}/#'
        )
        # for connection
        self.my_hw_node_id = gma().replace(':', '')[:8]
        self.my_hw_hex_id = f'!{self.my_hw_node_id}'
        self.my_hw_int_id = int(f'0x{self.my_hw_node_id}', base=16)
        #
        self.client = mqtt.Client()
        self.client.on_message = self.on_message
        self.client.on_connect = self.on_connect
        self.client.username_pw_set(self.cfg.MQTT.User, self.cfg.MQTT.Password)
        #
        self.common = CommonMQTT(self.name)
        self.common.set_client(self.client)
        self.common.set_logger(logger)
        self.common.set_config(cfg)
        # Crypto class
        self.crypto = MQTTCrypto()
        #
        StreamInterface.__init__(
            self, debugOut=debugOut, noProto=noProto, connectNow=connectNow
        )

    def close(self):
        """Close a connection to the device"""
        self.logger.info("Closing MQTT connection")
        StreamInterface.close(self)
        self._wantExit = True
        self.common.set_exit(True)

    def connect(self):
        """Connect to MQTT and emulate device"""
        if not self.cfg.MQTT.Enabled:
            return
        self.connection_thread = Thread(target=self.common.run_loop, daemon=True)
        self.connection_thread.start()

    def on_message(self, client, userdata, msg):
        """
        on_message - MQTT callback for message event
        """
        try:
            self.on_message_wrapped(client, userdata, msg)
        except Exception as exc:  # pylint:disable=broad-exception-caught
            self.logger.error('Exception in on_message_wrapped: %s -> %s', repr(exc), msg.payload)

    def on_message_wrapped(self, _client, _userdata, msg):
        """
        on_message_wrapped - safe MQTT callback for message event
        """
        # skip node status messages
        if msg.payload in [b'online', b'offline']:
            return
        # skip json messages for now
        json_msg = ''
        try:
            json_msg = json.loads(msg.payload)
        except Exception:  # pylint:disable=broad-exception-caught
            pass
        if len(json_msg) > 0:
            return
        #
        try:
            mqtt_incoming = mqtt_pb2.ServiceEnvelope().FromString(msg.payload)  # pylint:disable=no-member
        except Exception as exc:  # pylint:disable=broad-except
            self.logger.error("failed to decode incoming MQTT message: %s, %s", exc, str(msg.payload), exc_info=True)
            return

        full = json_format.MessageToDict(mqtt_incoming.packet)
        full['channel_id'] = mqtt_incoming.channel_id
        full['gateway_id'] = mqtt_incoming.gateway_id
        # drop our messages or messages without from
        if not full.get('from') or full.get('from', 0) == self.my_hw_int_id:
            return
        # process encrypted messages
        if full.get('encrypted'):
            full['decoded'] = json_format.MessageToDict(self.crypto.decrypt_packet(full))
        # drop messages without decoded
        if not full.get('decoded', None):
            self.logger.error("No decoded message in MQTT message: %s", full)
            return
        # Reassemble message
        new_packet = {
            'from': full['from'],
            'to': full['to'],
            'decoded': full['decoded'],
            'id': full.get('id', 0),
            'rxTime': full.get('rxTime', int(time.time())),
            'hopLimit': full.get('hopLimit', 3),
            'viaMqtt': True,
        }

        # Create final message. Convert it to protobuf
        new_msg = mesh_pb2.MeshPacket()  # pylint:disable=no-member
        radio_msg = json_format.ParseDict(new_packet, new_msg)

        try:
            self._handlePacketFromRadio(radio_msg)
        except Exception as exc:  # pylint:disable=broad-except
            self.logger.error(exc)

    def on_connect(self, client, _userdata, _flags, result_code):
        """
        on_connect - MQTT callback for connect event
        """
        self.logger.info(f"Connected with result code {str(result_code)}")
        client.subscribe(self.topic)
        # initialize interface
        self._startConfig()

    # pylint:disable=arguments-differ,unused-argument,no-member
    def sendData(self, msg, destinationId=BROADCAST_ADDR, portNum=PortNum.TEXT_MESSAGE_APP, **kwargs):
        """
        Send Meshtastic data message
        """
        if str(destinationId) == "-1":
            return
        packet_to = (
            # pylint:disable=line-too-long
            int(f"0x{str(destinationId).removeprefix('!')}", base=16) if destinationId != BROADCAST_ADDR else BROADCAST_NUM
        )
        self.logger.info(f"Sending data to {destinationId} with portNum {portNum} and message {msg}")
        # Create first message without from
        original_mqtt_message = mqtt_pb2.ServiceEnvelope()  # pylint:disable=no-member
        original_mqtt_message.channel_id = self.cfg.MQTT.Channel
        original_mqtt_message.gateway_id = self.my_hw_hex_id
        original_mqtt_message.packet.to = packet_to
        original_mqtt_message.packet.hop_limit = 2
        original_mqtt_message.packet.id = self._generatePacketId()
        original_mqtt_message.packet.rx_time = int(time.time())
        original_mqtt_message.packet.decoded.portnum = portNum
        original_mqtt_message.packet.decoded.payload = msg

        # Create second message from first one and add from
        as_dict = json_format.MessageToDict(original_mqtt_message.packet)
        as_dict["from"] = self.my_hw_int_id

        # Create third message and combine first and second
        full = json_format.MessageToDict(original_mqtt_message)
        full['packet'] = as_dict

        # Create forth and final message. Convert it to protobuf
        new_msg = mqtt_pb2.ServiceEnvelope()  # pylint:disable=no-member
        mqtt_msg = json_format.ParseDict(full, new_msg)
        Thread(target=self.send_mqtt_message, args=(mqtt_msg,), daemon=True).start()

    def send_mqtt_message(self, mqtt_msg):
        """
        sendMQTTMessage - deliver message over MQTT. With retries.
        """
        for subtopic in ['c', 'e']:
            mqtt_topic = f"{self.cfg.MQTT.Topic}/2/{subtopic}/{self.cfg.MQTT.Channel}/{self.my_hw_hex_id}"
            for _ in range(3):
                result = self.client.publish(mqtt_topic, mqtt_msg.SerializeToString())
                self.logger.info(f"MQTT message sent with result: {result}")
                # Sleep time for LongFast
                time.sleep(30)

    def waitForConfig(self):
        """Wait for configuration"""
        return

    def getLongName(self):
        """
        Return this node long name
        """
        return f'MTG {self.my_hw_hex_id}'

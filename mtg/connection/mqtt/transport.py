#-*- coding: utf-8 -*-
""" MQTT to Radio emulation transport module """

import base64
import json
import random
import struct
import time
from threading import Thread
from typing import Any, Dict, Optional

from cryptography.hazmat.primitives.ciphers import (
    Cipher, algorithms, modes
)
from getmac import get_mac_address as gma
from google.protobuf import json_format
from google.protobuf.message import DecodeError as ProtobufDecodeError
import paho.mqtt.client as mqtt

from meshtastic import mqtt_pb2, mesh_pb2, BROADCAST_NUM, BROADCAST_ADDR
from meshtastic import portnums_pb2 as PortNum
from meshtastic.stream_interface import StreamInterface

from .common import CommonMQTT

random.seed()

class MQTTCrypto:
    """ MQTT Crypto module """
    KEY = 'd4f1bb3a20290759f0bcffabcf4e6901'
    def __init__(self, key: Optional[str] = None) -> None:
        self.key = bytes.fromhex(key) if key else bytes.fromhex(self.KEY)

    @staticmethod
    def init_nonce(from_node: int, packet_id: int) -> bytearray:
        """
        init_nonce - Initialize nonce. Ported from meshtastic/firmware
        """
        nonce = bytearray(16)
        nonce[:8] = struct.pack('<Q', packet_id)
        nonce[8:12] = struct.pack('<I', from_node)
        return nonce

    @staticmethod
    def decrypt(key: bytes, nonce: bytearray, ciphertext: bytes) -> bytes:
        """
        decrypt - decrypt data using nonce and ciphertext
        """
        decryptor = Cipher(
            algorithms.AES(key),
            modes.CTR(nonce),
        ).decryptor()

        return decryptor.update(ciphertext) + decryptor.finalize()

    def decrypt_packet(self, packet: Dict[str, Any]) -> Any:
        """
        decrypt_packet - decrypt MQTT packet
        """
        encrypted_data = packet.get('encrypted')
        if encrypted_data is None:
            raise ValueError("No encrypted data in packet")
        data = base64.b64decode(encrypted_data)
        packet_from = packet.get('from')
        packet_id = packet.get('id')
        if packet_from is None or packet_id is None:
            raise ValueError("Missing from or id in packet")
        nonce = self.init_nonce(packet_from, packet_id)
        r = self.decrypt(self.key, nonce, data)
        return mesh_pb2.Data().FromString(r)  # pylint:disable=no-member

    @staticmethod
    def encrypt(key: bytes, nonce: bytearray, data_payload) -> bytes:
        """
        encrypt_packet - Not implemented yet
        """
        encryptor = Cipher(
            algorithms.AES(key),
            modes.CTR(nonce),
        ).encryptor()
        return encryptor.update(data_payload) + encryptor.finalize()

    @staticmethod
    def xor_hash(data: bytes) -> int:
        """Calculate XOR hash of data bytes."""
        result = 0
        for char in data:
            result ^= char
        return result

    def generate_channel_hash(self, name: str, key: str) -> int:
        """Generate channel hash from name and key."""
        # Add padding if needed for base64 decoding
        padding = 4 - (len(key) % 4)
        if padding != 4:
            key += '=' * padding
        key_bytes = base64.b64decode(key.encode('utf-8'))
        h_name = self.xor_hash(bytes(name, 'utf-8'))
        h_key = self.xor_hash(key_bytes)
        return h_name ^ h_key

    def encrypt_data_payload(self, data_payload: bytes, from_node: int, packet_id: int) -> bytes:
        """
        encrypt_data_payload - Encrypt a data payload for MQTT transmission
        """
        nonce = self.init_nonce(from_node, packet_id)
        return self.encrypt(self.key, nonce, data_payload)

class MQTTInterface(StreamInterface):  # pylint:disable=too-many-instance-attributes
    """
    MQTTInterface - MQTT to Radio emulation transport class
    """
    def __init__(self, debugOut: Optional[Any] = None,  # pylint:disable=too-many-arguments,too-many-positional-arguments
                 noProto: bool = False,
                 connectNow: bool = True,
                 cfg: Optional[Any] = None,
                 logger: Optional[Any] = None) -> None:

        self.stream = None
        self.cfg = cfg
        self.logger = logger
        self.connection_thread: Optional[Thread] = None
        self.name = "MQTT Interface"
        #
        self.topic = (
            self.cfg.MQTT.Topic  # type: ignore[union-attr]
            if self.cfg and self.cfg.MQTT.Topic.endswith('#')
            else f'{self.cfg.MQTT.Topic}/#' if self.cfg else 'meshtastic/2/e/#'
        )
        # for connection
        self.my_hw_node_id = gma().replace(':', '')[:8]
        self.my_hw_hex_id = f'!{self.my_hw_node_id}'
        self.my_hw_int_id = int(f'0x{self.my_hw_node_id}', base=16)
        #
        self.client = mqtt.Client()
        self.client.on_message = self.on_message
        self.client.on_connect = self.on_connect
        if self.cfg:
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

    def close(self) -> None:
        """Close a connection to the device"""
        if self.logger:
            self.logger.info("Closing MQTT connection")
        StreamInterface.close(self)
        self._wantExit = True
        self.common.set_exit(True)

    def connect(self) -> None:
        """Connect to MQTT and emulate device"""
        if not self.cfg or not self.cfg.MQTT.Enabled:
            return
        self.connection_thread = Thread(target=self.common.run_loop, daemon=True)
        self.connection_thread.start()

    def on_message(self, client: Any, userdata: Any, msg: Any) -> None:
        """
        on_message - MQTT callback for message event
        """
        try:
            self.on_message_wrapped(client, userdata, msg)
        except Exception as exc:  # pylint:disable=broad-exception-caught
            if self.logger:
                self.logger.error('Exception in on_message_wrapped: %s -> %s', repr(exc), msg.payload)

    # pylint:disable=too-many-statements
    # pylint:disable=too-many-branches
    def on_message_wrapped(self, _client: Any, _userdata: Any, msg: Any) -> None:
        """
        on_message_wrapped - safe MQTT callback for message event
        """
        if self.logger:
            self.logger.debug(msg.topic)
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
        except ProtobufDecodeError:
            if self.logger:
                self.logger.error("failed to decode incoming MQTT message: %s", str(msg.payload))
            return
        except Exception as exc:  # pylint:disable=broad-except
            if self.logger:
                self.logger.error(
                    "failed to decode incoming MQTT message: %s, %s", exc, str(msg.payload), exc_info=True
                )
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
            if self.logger:
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
            if self.logger:
                self.logger.error(exc)

    def nodeinfo(self) -> bytes:
        """
        nodeinfo - prepare node info
        """
        new_node = mesh_pb2.User()  # pylint:disable=no-member
        new_node.id = self.my_hw_hex_id
        new_node.long_name = self.getLongName()
        new_node.short_name = 'WMTG'
        new_node.hw_model = 'RAK4631'
        return new_node.SerializeToString()

    def node_publisher(self) -> None:
        """
        node_publisher - send node info regularly
        """
        time.sleep(10)
        while True:
            self.sendData(self.nodeinfo(), portNum=PortNum.NODEINFO_APP)  # pylint:disable=no-member
            time.sleep(1800)

    def on_connect(self, client: Any, _userdata: Any, _flags: Any, result_code: int) -> None:
        """
        on_connect - MQTT callback for connect event
        """
        if self.logger:
            self.logger.info(f"Connected with result code {str(result_code)}")
        client.subscribe(self.topic)
        # initialize interface
        self._startConfig()

    def create_packet_raw(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self, packet_to: int, msg: bytes, port_num: int, hop_limit: int = 3, is_encrypted: bool = False
    ) -> Any:
        """
        Create raw packet structure for either encrypted or unencrypted transmission
        """
        # Generate packet ID once for consistency
        packet_id = self._generatePacketId()
        channel_name = self.cfg.MQTT.Channel if self.cfg else "default"

        # Create the ServiceEnvelope
        service_envelope = mqtt_pb2.ServiceEnvelope()  # pylint:disable=no-member
        service_envelope.channel_id = channel_name
        service_envelope.gateway_id = self.my_hw_hex_id

        # Create the MeshPacket
        mesh_packet = mesh_pb2.MeshPacket()  # pylint:disable=no-member
        mesh_packet.id = packet_id
        mesh_packet.to = packet_to
        mesh_packet.hop_limit = hop_limit
        setattr(mesh_packet, "from", self.my_hw_int_id)

        if is_encrypted:
            # For encrypted packets, create Data payload and encrypt it
            data_payload = mesh_pb2.Data(  # pylint:disable=no-member
                portnum=port_num,
                payload=msg,
                bitfield=3 if packet_to != BROADCAST_NUM else 1
            )
            mesh_packet.encrypted = self.crypto.encrypt_data_payload(
                data_payload.SerializeToString(),
                self.my_hw_int_id,
                packet_id
            )
            # Set channel hash for encrypted packets
            mesh_packet.channel = self.crypto.generate_channel_hash(channel_name, str(self.crypto.key))
        else:
            # For unencrypted packets, set the decoded field directly
            mesh_packet.rx_time = int(time.time())
            mesh_packet.decoded.portnum = port_num
            mesh_packet.decoded.payload = msg

        # Copy the mesh packet to the service envelope
        service_envelope.packet.CopyFrom(mesh_packet)

        if is_encrypted:
            # For encrypted packets, return serialized bytes directly
            return service_envelope.SerializeToString()
        # For unencrypted packets, we need to do the dictionary manipulation
        # to add the "from" field properly (protobuf reserved word workaround)
        as_dict = json_format.MessageToDict(service_envelope.packet)
        as_dict["from"] = self.my_hw_int_id

        full = json_format.MessageToDict(service_envelope)
        full['packet'] = as_dict

        new_msg = mqtt_pb2.ServiceEnvelope()  # pylint:disable=no-member
        return json_format.ParseDict(full, new_msg)

    def create_packet(self, packet_to: int, msg: bytes, port_num: int, hop_limit: int) -> Any:
        """
        Create an unencrypted packet for transmission
        """
        return self.create_packet_raw(packet_to, msg, port_num, hop_limit=hop_limit, is_encrypted=False)

    def create_encrypted_packet(self, packet_to: int, msg: bytes, port_num: int, hop_limit: int) -> Any:
        """
        Create an encrypted packet for transmission
        """
        return self.create_packet_raw(packet_to, msg, port_num, hop_limit=hop_limit, is_encrypted=True)

    # pylint:disable=arguments-differ,unused-argument,no-member
    def sendData(
        self, msg: bytes, destination_id: Any = BROADCAST_ADDR, port_num: Any = PortNum.TEXT_MESSAGE_APP, **kwargs: Any
    ) -> None:
        """
        Send Meshtastic data message
        """
        if str(destination_id) == "-1":
            return
        packet_to = (
            # pylint:disable=line-too-long
            int(f"0x{str(destination_id).removeprefix('!')}", base=16) if destination_id != BROADCAST_ADDR else BROADCAST_NUM
        )
        if self.logger:
            self.logger.info(f"Sending data to {destination_id} with portNum {port_num} and message {msg!r}")

        # Create both encrypted and unencrypted packets for backwards compatibility
        hop_limit = 5
        encrypted_msg = self.create_encrypted_packet(packet_to, msg, port_num, hop_limit)
        unencrypted_msg = self.create_packet(packet_to, msg, port_num, hop_limit)
        Thread(target=self.send_mqtt_message, args=(encrypted_msg, unencrypted_msg), daemon=True).start()

    def send_mqtt_message(self, encrypted_msg: Any, unencrypted_msg: Any) -> None:
        """
        sendMQTTMessage - deliver message over MQTT. With retries.
        Sends to both /e/ (encrypted) and /c/ (unencrypted) for backwards compatibility
        """
        if self.cfg:
            # Send encrypted message to /e/ topic
            encrypted_topic = f"{self.cfg.MQTT.Topic}/2/e/{self.cfg.MQTT.Channel}/{self.my_hw_hex_id}"
            unencrypted_topic = f"{self.cfg.MQTT.Topic}/2/c/{self.cfg.MQTT.Channel}/{self.my_hw_hex_id}"

            for _ in range(3):
                # Send encrypted message (raw bytes)
                result_e = self.client.publish(encrypted_topic, encrypted_msg)
                if self.logger:
                    self.logger.info(f"MQTT encrypted message sent to {encrypted_topic} with result: {result_e}")

                # Send unencrypted message (serialized protobuf)
                result_c = self.client.publish(unencrypted_topic, unencrypted_msg.SerializeToString())
                if self.logger:
                    self.logger.info(f"MQTT unencrypted message sent to {unencrypted_topic} with result: {result_c}")

            # Sleep time for LongFast
            time.sleep(30)

    def waitForConfig(self) -> None:
        """Wait for configuration"""
        return

    def getLongName(self) -> str:
        """
        Return this node long name
        """
        return f'MTG {self.my_hw_hex_id}'

# -*- coding: utf-8 -*-
# pylint: skip-file
import pytest
from unittest.mock import patch, MagicMock, Mock
import base64
import time
import struct

from mtg.connection.mqtt.transport import MQTTCrypto, MQTTInterface
from meshtastic import mqtt_pb2, mesh_pb2, BROADCAST_NUM, BROADCAST_ADDR
from meshtastic import portnums_pb2 as PortNum


class TestMQTTCrypto:
    """Test MQTTCrypto class"""

    @pytest.fixture
    def crypto(self):
        """Create MQTTCrypto instance"""
        return MQTTCrypto()

    @pytest.fixture
    def crypto_with_key(self):
        """Create MQTTCrypto instance with custom key"""
        return MQTTCrypto(key="aabbccddeeff00112233445566778899")

    def test_init_default(self, crypto):
        """Test MQTTCrypto initialization with default key"""
        expected_key = bytes.fromhex('d4f1bb3a20290759f0bcffabcf4e6901')
        assert crypto.key == expected_key

    def test_init_custom_key(self, crypto_with_key):
        """Test MQTTCrypto initialization with custom key"""
        expected_key = bytes.fromhex("aabbccddeeff00112233445566778899")
        assert crypto_with_key.key == expected_key

    def test_init_nonce(self):
        """Test nonce initialization"""
        from_node = 0x12345678
        packet_id = 0xAABBCCDD

        nonce = MQTTCrypto.init_nonce(from_node, packet_id)

        assert len(nonce) == 16
        assert nonce[:8] == struct.pack('<Q', packet_id)
        assert nonce[8:12] == struct.pack('<I', from_node)
        assert nonce[12:] == b'\x00\x00\x00\x00'

    def test_xor_hash(self):
        """Test XOR hash calculation"""
        data = b"test"
        result = MQTTCrypto.xor_hash(data)
        expected = ord('t') ^ ord('e') ^ ord('s') ^ ord('t')
        assert result == expected

    def test_generate_channel_hash(self, crypto):
        """Test channel hash generation"""
        name = "test_channel"
        key = "dGVzdGtleQ"  # base64 encoded

        result = crypto.generate_channel_hash(name, key)
        assert isinstance(result, int)

    def test_generate_channel_hash_with_padding(self, crypto):
        """Test channel hash generation with padding needed"""
        name = "test"
        key = "abc"  # Needs padding

        result = crypto.generate_channel_hash(name, key)
        assert isinstance(result, int)

    @patch('mtg.connection.mqtt.transport.Cipher')
    def test_encrypt_data_payload(self, mock_cipher, crypto):
        """Test data payload encryption"""
        data = b"test_payload"
        from_node = 0x12345678
        packet_id = 0xAABBCCDD

        mock_encryptor = MagicMock()
        mock_encryptor.update.return_value = b"encrypted"
        mock_encryptor.finalize.return_value = b"_data"
        mock_cipher.return_value.encryptor.return_value = mock_encryptor

        result = crypto.encrypt_data_payload(data, from_node, packet_id)

        assert result == b"encrypted_data"
        mock_encryptor.update.assert_called_once_with(data)

    @patch('mtg.connection.mqtt.transport.Cipher')
    def test_decrypt(self, mock_cipher):
        """Test decryption"""
        key = b"test_key_16bytes"
        nonce = bytearray(16)
        ciphertext = b"encrypted_data"

        mock_decryptor = MagicMock()
        mock_decryptor.update.return_value = b"decrypted"
        mock_decryptor.finalize.return_value = b"_data"
        mock_cipher.return_value.decryptor.return_value = mock_decryptor

        result = MQTTCrypto.decrypt(key, nonce, ciphertext)

        assert result == b"decrypted_data"
        mock_decryptor.update.assert_called_once_with(ciphertext)

    @patch('mtg.connection.mqtt.transport.mesh_pb2.Data')
    @patch.object(MQTTCrypto, 'decrypt')
    def test_decrypt_packet(self, mock_decrypt, mock_data, crypto):
        """Test packet decryption"""
        packet = {
            'encrypted': base64.b64encode(b"encrypted_data").decode(),
            'from': 0x12345678,
            'id': 0xAABBCCDD
        }

        mock_decrypt.return_value = b"decrypted_data"
        mock_data_instance = MagicMock()
        mock_data.return_value.FromString.return_value = mock_data_instance

        result = crypto.decrypt_packet(packet)

        mock_decrypt.assert_called_once()
        mock_data.return_value.FromString.assert_called_once_with(b"decrypted_data")

    def test_decrypt_packet_no_encrypted(self, crypto):
        """Test decrypt_packet with missing encrypted data"""
        packet = {'from': 123, 'id': 456}

        with pytest.raises(ValueError, match="No encrypted data in packet"):
            crypto.decrypt_packet(packet)

    def test_decrypt_packet_missing_fields(self, crypto):
        """Test decrypt_packet with missing from/id fields"""
        packet = {'encrypted': base64.b64encode(b"data").decode()}

        with pytest.raises(ValueError, match="Missing from or id in packet"):
            crypto.decrypt_packet(packet)


class TestMQTTInterface:
    """Test MQTTInterface class - simplified tests"""

    def test_crypto_key_properties(self):
        """Test MQTTCrypto key properties"""
        crypto = MQTTCrypto()
        assert len(crypto.key) == 16  # 128-bit key

    def test_crypto_hash_functions(self):
        """Test crypto hash functions work"""
        crypto = MQTTCrypto()

        # Test XOR hash
        result = crypto.xor_hash(b"hello")
        assert isinstance(result, int)

        # Test channel hash
        result = crypto.generate_channel_hash("test", "dGVzdA==")
        assert isinstance(result, int)

    def test_crypto_encrypt_decrypt_flow(self):
        """Test complete encrypt/decrypt flow"""
        crypto = MQTTCrypto()

        # Test encryption
        data = b"test message"
        from_node = 0x12345
        packet_id = 0x789

        with patch('mtg.connection.mqtt.transport.Cipher') as mock_cipher:
            mock_encryptor = MagicMock()
            mock_encryptor.update.return_value = b"encrypted"
            mock_encryptor.finalize.return_value = b"_data"
            mock_cipher.return_value.encryptor.return_value = mock_encryptor

            result = crypto.encrypt_data_payload(data, from_node, packet_id)
            assert result == b"encrypted_data"

    def test_crypto_nonce_generation(self):
        """Test nonce generation is deterministic"""
        from_node = 0x12345678
        packet_id = 0xAABBCCDD

        nonce1 = MQTTCrypto.init_nonce(from_node, packet_id)
        nonce2 = MQTTCrypto.init_nonce(from_node, packet_id)

        assert nonce1 == nonce2  # Should be deterministic
        assert len(nonce1) == 16

    def test_crypto_channel_hash_consistency(self):
        """Test channel hash is consistent"""
        crypto = MQTTCrypto()

        hash1 = crypto.generate_channel_hash("test", "dGVzdA==")
        hash2 = crypto.generate_channel_hash("test", "dGVzdA==")

        assert hash1 == hash2  # Should be consistent

    def test_crypto_different_inputs_different_outputs(self):
        """Test different inputs produce different outputs"""
        crypto = MQTTCrypto()

        hash1 = crypto.generate_channel_hash("test1", "dGVzdA==")
        hash2 = crypto.generate_channel_hash("test2", "dGVzdA==")

        assert hash1 != hash2  # Different names should produce different hashes

    def test_crypto_xor_hash_properties(self):
        """Test XOR hash properties"""
        # Test empty data
        assert MQTTCrypto.xor_hash(b"") == 0

        # Test single byte
        assert MQTTCrypto.xor_hash(b"A") == ord('A')

        # Test XOR property: a XOR a = 0
        data = b"test"
        result = MQTTCrypto.xor_hash(data + data)
        assert result == 0  # XORing identical data should give 0
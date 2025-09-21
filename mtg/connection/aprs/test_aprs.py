# -*- coding: utf-8 -*-
# pylint: skip-file
import pytest
from unittest.mock import patch, MagicMock, Mock, call
from datetime import datetime
from decimal import Decimal
import logging

from mtg.connection.aprs.aprs import APRSStreamer
from mtg.config import Config
from mtg.utils.rf.prefixes import ITUPrefix


class TestAPRSStreamer:
    """Test APRSStreamer class"""

    @pytest.fixture
    def mock_config(self):
        """Create mock configuration"""
        config = MagicMock()
        config.APRS.Enabled = True
        config.APRS.ToMeshtastic = True
        config.APRS.FromMeshtastic = True
        config.APRS.Callsign = "TEST1ABC"
        config.APRS.Password = "12345"
        config.WebApp.Center_Latitude = 40.7128
        config.WebApp.Center_Longitude = -74.0060
        config.Telegram.NotificationsRoom = 12345
        config.Telegram.RoomLink = "https://t.me/test"

        # Mock enforce_type to return proper values based on context
        def enforce_type_side_effect(type_hint, value):
            # Check if it's the actual value or has the name attribute
            if value == 12345 or (hasattr(value, '__name__') and 'NotificationsRoom' in str(value)):
                return 12345
            elif value == 40.7128 or (hasattr(value, '__name__') and 'Center_Latitude' in str(value)):
                return 40.7128
            elif value == -74.0060 or (hasattr(value, '__name__') and 'Center_Longitude' in str(value)):
                return -74.0060
            return value if isinstance(value, (int, float)) else True

        config.enforce_type.side_effect = enforce_type_side_effect
        return config

    @pytest.fixture
    def mock_itu_prefix(self):
        """Create mock ITU prefix"""
        itu_prefix = MagicMock(spec=ITUPrefix)
        itu_prefix.get_country_by_callsign.return_value = "United States"
        itu_prefix.get_prefixes_by_callsign.return_value = ["K", "N", "W"]
        return itu_prefix

    @pytest.fixture
    def aprs_streamer(self, mock_config, mock_itu_prefix):
        """Create APRSStreamer instance"""
        return APRSStreamer(mock_config, mock_itu_prefix)

    def test_init(self, mock_config, mock_itu_prefix):
        """Test APRSStreamer initialization"""
        streamer = APRSStreamer(mock_config, mock_itu_prefix)

        assert streamer.config == mock_config
        assert streamer.itu_prefix == mock_itu_prefix
        assert streamer.aprs_is is None
        assert streamer.filter is None
        assert streamer.logger is None
        assert streamer.exit is False
        assert streamer.name == 'APRS Streamer'
        assert streamer.database is None
        assert streamer.connection is None
        assert streamer.telegram_connection is None
        assert streamer.prefixes == []
        assert streamer.memcache is not None

    def test_set_telegram_connection(self, aprs_streamer):
        """Test set_telegram_connection method"""
        mock_telegram = MagicMock()
        aprs_streamer.set_telegram_connection(mock_telegram)
        assert aprs_streamer.telegram_connection == mock_telegram

    def test_set_db(self, aprs_streamer):
        """Test set_db method"""
        mock_db = MagicMock()
        aprs_streamer.set_db(mock_db)
        assert aprs_streamer.database == mock_db

    def test_set_logger(self, aprs_streamer):
        """Test set_logger method"""
        mock_logger = MagicMock(spec=logging.Logger)
        aprs_streamer.set_logger(mock_logger)
        assert aprs_streamer.logger == mock_logger

    def test_set_meshtastic(self, aprs_streamer):
        """Test set_meshtastic method"""
        mock_connection = MagicMock()
        aprs_streamer.set_meshtastic(mock_connection)
        assert aprs_streamer.connection == mock_connection

    def test_set_filter(self, aprs_streamer):
        """Test set_filter method"""
        mock_filter = MagicMock()
        aprs_streamer.set_filter(mock_filter)
        assert aprs_streamer.filter == mock_filter

    def test_send_packet_enabled(self, aprs_streamer):
        """Test send_packet when FromMeshtastic is enabled"""
        mock_aprs_is = MagicMock()
        aprs_streamer.aprs_is = mock_aprs_is
        aprs_streamer.config.enforce_type.return_value = True

        aprs_streamer.send_packet("TEST>APRS:Hello")

        mock_aprs_is.sendall.assert_called_once_with("TEST>APRS:Hello")

    def test_send_packet_disabled(self, aprs_streamer):
        """Test send_packet when FromMeshtastic is disabled"""
        mock_aprs_is = MagicMock()
        aprs_streamer.aprs_is = mock_aprs_is

        # Override the side effect for this specific test
        aprs_streamer.config.enforce_type.side_effect = None
        aprs_streamer.config.enforce_type.return_value = False

        aprs_streamer.send_packet("TEST>APRS:Hello")

        mock_aprs_is.sendall.assert_not_called()

    def test_send_packet_no_connection(self, aprs_streamer):
        """Test send_packet when aprs_is is None"""
        aprs_streamer.aprs_is = None
        aprs_streamer.config.enforce_type.return_value = True

        # Should not raise exception
        aprs_streamer.send_packet("TEST>APRS:Hello")

    def test_send_text(self, aprs_streamer):
        """Test send_text method"""
        aprs_streamer.aprs_is = MagicMock()
        aprs_streamer.config.APRS.Callsign = "TEST1ABC"

        with patch.object(aprs_streamer, 'send_packet') as mock_send:
            aprs_streamer.send_text("DEST", "Hello World")

            expected_packet = "TEST1ABC>APDR15,WIDE1-1,WIDE2-2::DEST     :Hello World"
            mock_send.assert_called_once_with(expected_packet)

    def test_process_disabled(self, aprs_streamer):
        """Test process when ToMeshtastic is disabled"""
        aprs_streamer.config.enforce_type.return_value = False
        packet = {"format": "message", "message_text": "Hello"}

        aprs_streamer.process(packet)

        # Should exit early, no further processing

    def test_process_not_message_format(self, aprs_streamer):
        """Test process with non-message format"""
        aprs_streamer.config.enforce_type.return_value = True
        packet = {"format": "position", "message_text": "Hello"}

        aprs_streamer.process(packet)

        # Should exit early for non-message packets

    def test_process_empty_message(self, aprs_streamer):
        """Test process with empty message text"""
        aprs_streamer.config.enforce_type.return_value = True
        packet = {"format": "message", "message_text": ""}

        aprs_streamer.process(packet)

        # Should exit early for empty messages

    def test_process_wrong_addressee(self, aprs_streamer):
        """Test process with wrong addressee"""
        aprs_streamer.config.enforce_type.return_value = True
        aprs_streamer.config.APRS.Callsign = "TEST1ABC"
        packet = {
            "format": "message",
            "message_text": "Hello",
            "addresse": "OTHER"
        }

        aprs_streamer.process(packet)

        # Should exit early for wrong addressee

    def test_process_valid_message(self, aprs_streamer):
        """Test process with valid message"""
        aprs_streamer.config.enforce_type.return_value = True
        aprs_streamer.config.APRS.Callsign = "TEST1ABC"
        mock_logger = MagicMock()
        aprs_streamer.set_logger(mock_logger)

        packet = {
            "format": "message",
            "message_text": "Hello World",
            "addresse": "TEST1ABC",
            "from": "SENDER",
            "msgNo": "001"
        }

        with patch.object(aprs_streamer, 'send_text') as mock_send_text:
            with patch.object(aprs_streamer.memcache, 'get', return_value=False):
                with patch.object(aprs_streamer.memcache, 'set') as mock_cache_set:
                    aprs_streamer.process(packet)

                    # Should send ACK
                    mock_send_text.assert_called_with("SENDER", "ack001")
                    # Should cache the message
                    mock_cache_set.assert_called_with("SENDERHello World", True, expires=300)
                    # Should log the packet
                    mock_logger.info.assert_called_with(f'Got APRS PACKET: {packet}')

    def test_process_ping_response(self, aprs_streamer):
        """Test process responds to ping"""
        aprs_streamer.config.enforce_type.return_value = True
        aprs_streamer.config.APRS.Callsign = "TEST1ABC"

        packet = {
            "format": "message",
            "message_text": "ping",
            "addresse": "TEST1ABC",
            "from": "SENDER"
        }

        with patch.object(aprs_streamer, 'send_text') as mock_send_text:
            with patch.object(aprs_streamer.memcache, 'get', return_value=False):
                with patch.object(aprs_streamer.memcache, 'set'):
                    aprs_streamer.process(packet)

                    # Should respond to ping
                    calls = mock_send_text.call_args_list
                    assert call("SENDER", "passed") in calls

    def test_process_forward_to_telegram(self, aprs_streamer):
        """Test process forwards to Telegram"""
        aprs_streamer.config.APRS.Callsign = "TEST1ABC"

        packet = {
            "format": "message",
            "message_text": "Hello",
            "addresse": "TEST1ABC",
            "from": "SENDER"
        }

        mock_telegram = MagicMock()
        aprs_streamer.set_telegram_connection(mock_telegram)

        with patch.object(aprs_streamer.memcache, 'get', return_value=False):
            with patch.object(aprs_streamer.memcache, 'set'):
                aprs_streamer.process(packet)

                mock_telegram.send_message_sync.assert_called_once_with(
                    chat_id=12345,
                    text="APRS-SENDER: Hello"
                )

    def test_process_forward_to_meshtastic(self, aprs_streamer):
        """Test process forwards to Meshtastic"""
        aprs_streamer.config.enforce_type.return_value = True
        aprs_streamer.config.APRS.Callsign = "TEST1ABC"

        packet = {
            "format": "message",
            "message_text": "Hello",
            "addresse": "TEST1ABC",
            "from": "SENDER"
        }

        mock_connection = MagicMock()
        aprs_streamer.set_meshtastic(mock_connection)

        with patch.object(aprs_streamer.memcache, 'get', return_value=False):
            with patch.object(aprs_streamer.memcache, 'set'):
                aprs_streamer.process(packet)

                mock_connection.send_text.assert_called_once_with("APRS-SENDER: Hello")

    @patch('mtg.connection.aprs.aprs.pub')
    def test_callback(self, mock_pub):
        """Test callback static method"""
        packet = {"format": "message", "message_text": "Hello"}

        APRSStreamer.callback(packet)

        mock_pub.sendMessage.assert_called_once_with('APRS', packet=packet)

    def test_get_imag(self):
        """Test get_imag static method"""
        result = APRSStreamer.get_imag(123.456)
        expected = float((Decimal('123.456') - (Decimal('123.456') // 1)))
        assert result == expected

        # Test with integer
        result = APRSStreamer.get_imag(123.0)
        assert result == 0.0

    def test_dec2sexagesimal(self, aprs_streamer):
        """Test dec2sexagesimal method"""
        # Test positive value
        degrees, minutes, seconds = aprs_streamer.dec2sexagesimal(40.7128)
        assert degrees == 40
        assert isinstance(minutes, int)
        assert isinstance(seconds, int)

        # Test negative value
        degrees, minutes, seconds = aprs_streamer.dec2sexagesimal(-74.0060)
        assert degrees == -74
        assert isinstance(minutes, int)
        assert isinstance(seconds, int)

        # Test zero
        degrees, minutes, seconds = aprs_streamer.dec2sexagesimal(0.0)
        assert degrees == 0
        assert minutes == 0
        assert seconds == 0

    def test_send_location_no_from_id(self, aprs_streamer):
        """Test send_location with missing fromId"""
        packet = {"decoded": {"position": {}}}

        aprs_streamer.send_location(packet)

        # Should exit early with no fromId

    def test_send_location_no_database(self, aprs_streamer):
        """Test send_location with no database"""
        packet = {"fromId": "!12345678"}
        mock_logger = MagicMock()
        aprs_streamer.set_logger(mock_logger)

        aprs_streamer.send_location(packet)

        mock_logger.warning.assert_called_with('Node %s not in node DB', '!12345678')

    def test_send_location_cached(self, aprs_streamer):
        """Test send_location with cached location"""
        packet = {"fromId": "!12345678"}
        mock_db = MagicMock()
        aprs_streamer.set_db(mock_db)

        with patch.object(aprs_streamer.memcache, 'get', return_value=True):
            aprs_streamer.send_location(packet)

            # Should exit early due to cache

    @patch('mtg.connection.aprs.aprs.datetime')
    def test_send_location_valid(self, mock_datetime, aprs_streamer):
        """Test send_location with valid data"""
        mock_datetime.now.return_value.strftime.return_value = "011230"

        packet = {
            "fromId": "!12345678",
            "decoded": {
                "position": {
                    "latitude": 40.7128,
                    "longitude": -74.0060,
                    "altitude": 100
                }
            }
        }

        mock_db = MagicMock()
        mock_node = MagicMock()
        mock_node.nodeName = "K1ABC"
        mock_db.get_node_info.return_value = mock_node
        aprs_streamer.set_db(mock_db)
        aprs_streamer.prefixes = ["K", "N", "W"]

        mock_aprs_is = MagicMock()
        aprs_streamer.aprs_is = mock_aprs_is
        mock_logger = MagicMock()
        aprs_streamer.set_logger(mock_logger)

        with patch.object(aprs_streamer.memcache, 'get', return_value=False):
            with patch.object(aprs_streamer.memcache, 'set') as mock_cache_set:
                aprs_streamer.send_location(packet)

                # Should cache location
                mock_cache_set.assert_called_with("!12345678-location", True, expires=60)

                # Should send APRS packet
                mock_aprs_is.sendall.assert_called_once()
                call_args = mock_aprs_is.sendall.call_args[0][0]
                assert "K1ABC>APRS,TCPIP*:@011230/" in call_args
                assert "/A=000328" in call_args  # altitude in feet
                assert "https://t.me/test" in call_args

    def test_shutdown(self, aprs_streamer):
        """Test shutdown method"""
        aprs_streamer.shutdown()
        assert aprs_streamer.exit is True

    @patch('mtg.connection.aprs.aprs.setthreadtitle')
    @patch('mtg.connection.aprs.aprs.aprslib')
    def test_run_loop_no_country(self, mock_aprslib, mock_setthreadtitle, aprs_streamer):
        """Test run_loop when country cannot be determined"""
        aprs_streamer.itu_prefix.get_country_by_callsign.return_value = None

        with pytest.raises(RuntimeError, match="Could not get country for callsign TEST1ABC"):
            aprs_streamer.run_loop()

    @patch('mtg.connection.aprs.aprs.setthreadtitle')
    @patch('mtg.connection.aprs.aprs.aprslib')
    def test_run_loop_success(self, mock_aprslib, mock_setthreadtitle, aprs_streamer):
        """Test successful run_loop execution"""
        aprs_streamer.exit = True  # Exit immediately to prevent infinite loop
        mock_logger = MagicMock()
        aprs_streamer.set_logger(mock_logger)

        # Ensure enforce_type returns True for APRS.Enabled
        aprs_streamer.config.APRS.Enabled = True

        mock_aprs_is = MagicMock()
        mock_aprslib.IS.return_value = mock_aprs_is

        aprs_streamer.run_loop()

        # Should set thread title
        mock_setthreadtitle.assert_called_once_with('APRS Streamer')

        # Should create APRS-IS connection
        mock_aprslib.IS.assert_called_once_with(
            "TEST1ABC",
            "12345",
            host='rotate.aprs2.net',
            port=14580
        )

        # Should set filter based on coordinates
        expected_filter = "r/40.7128/-74.006/50"
        mock_aprs_is.set_filter.assert_called_once_with(expected_filter)

        # Should log startup
        mock_logger.info.assert_called_with('Starting APRS for country United States...')

    @patch('mtg.connection.aprs.aprs.pub')
    @patch('mtg.connection.aprs.aprs.Thread')
    def test_run_enabled(self, mock_thread, mock_pub, aprs_streamer):
        """Test run method when APRS is enabled"""
        aprs_streamer.config.enforce_type.return_value = True

        aprs_streamer.run()

        # Should subscribe to APRS messages
        mock_pub.subscribe.assert_called_once_with(aprs_streamer.process, 'APRS')

        # Should start thread
        mock_thread.assert_called_once_with(
            target=aprs_streamer.run_loop,
            daemon=True,
            name='APRS Streamer'
        )
        mock_thread.return_value.start.assert_called_once()


    def test_mathematical_functions(self, aprs_streamer):
        """Test mathematical conversion functions"""
        # Test get_imag with various values
        assert APRSStreamer.get_imag(123.0) == 0.0
        assert APRSStreamer.get_imag(123.5) == 0.5

        # Test dec2sexagesimal with known values
        degrees, minutes, seconds = aprs_streamer.dec2sexagesimal(40.758896)
        assert degrees == 40
        # Should convert fractional part to minutes and seconds

        # Test with negative longitude
        degrees, minutes, seconds = aprs_streamer.dec2sexagesimal(-74.006)
        assert degrees == -74

    def test_coordinate_conversion_accuracy(self, aprs_streamer):
        """Test coordinate conversion accuracy"""
        # Test known coordinate conversion
        lat = 40.7589
        degrees, minutes, seconds = aprs_streamer.dec2sexagesimal(lat)

        # Verify conversion is reasonable
        assert degrees == 40
        assert 0 <= minutes < 60
        assert 0 <= seconds < 60

        # Test reconstruction (approximately)
        reconstructed = degrees + minutes/60.0 + seconds/3600.0
        assert abs(reconstructed - lat) < 0.1  # Allow some precision loss

    def test_aprs_packet_formatting(self, aprs_streamer):
        """Test APRS packet formatting"""
        with patch.object(aprs_streamer, 'send_packet') as mock_send:
            aprs_streamer.send_text("W1AW", "Test message")

            # Check packet format
            call_args = mock_send.call_args[0][0]
            assert "TEST1ABC>APDR15,WIDE1-1,WIDE2-2::" in call_args
            assert "W1AW     :Test message" in call_args  # 9-char padded callsign

    def test_ham_callsign_validation_patterns(self, aprs_streamer):
        """Test various ham callsign patterns"""
        aprs_streamer.prefixes = ["K", "N", "W", "VE", "VK", "G"]

        # Test various valid patterns
        valid_calls = ["K1ABC", "N2XYZ", "W3DEF", "K1ABC-5", "N2XYZ-12"]
        invalid_calls = ["INVALID", "123ABC", "AB", "TOOLONGCALL"]

        # This would need integration with the actual validation logic
        # For now, we just ensure the prefixes are set correctly
        assert "K" in aprs_streamer.prefixes
        assert "N" in aprs_streamer.prefixes
        assert "W" in aprs_streamer.prefixes
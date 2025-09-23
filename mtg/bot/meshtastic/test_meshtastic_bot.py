# -*- coding: utf-8 -*-
# pylint: skip-file
import pytest
import time
import sys
from unittest.mock import MagicMock, patch

# Mock external dependencies to avoid import conflicts
sys.modules['meshtastic'] = MagicMock()
sys.modules['meshtastic.serial_interface'] = MagicMock()
sys.modules['meshtastic.portnums_pb2'] = MagicMock()
sys.modules['pubsub'] = MagicMock()
sys.modules['pubsub.pub'] = MagicMock()
sys.modules['requests'] = MagicMock()

from mtg.bot.meshtastic.meshtastic import MeshtasticBot


@pytest.fixture
def mock_database():
    """Mock database fixture"""
    db = MagicMock()
    db.get_node_record.return_value = (True, MagicMock(nodeName="TestNode"))
    db.get_stats.return_value = "Stats: Messages: 10"
    db.get_last_coordinates.return_value = (45.0, -90.0)
    db.store_location = MagicMock()
    db.store_message = MagicMock()
    db.set_coordinates = MagicMock()
    return db


@pytest.fixture
def mock_config():
    """Mock configuration fixture"""
    config = MagicMock()
    config.enforce_type.side_effect = lambda type_cls, value: type_cls(value) if value else type_cls()
    config.Meshtastic.NodeLogFile = "/tmp/test.csv"
    config.Meshtastic.Admin = "!12345678"
    config.Meshtastic.MaxHopCount = 3
    config.Meshtastic.WelcomeMessageEnabled = True
    config.Meshtastic.WelcomeMessage = "Welcome to the mesh!"
    config.Telegram.NotificationsEnabled = True
    config.Telegram.NotificationsRoom = 12345
    config.Telegram.Room = 67890
    config.Telegram.MapLinkEnabled = True
    config.Telegram.MapLink = "https://example.com/map?node=%s"
    config.WebApp.Center_Latitude = 45.0
    config.WebApp.Center_Longitude = -90.0
    config.DEFAULT.OpenWeatherKey = "test_key"
    return config


@pytest.fixture
def mock_meshtastic_connection():
    """Mock Meshtastic connection fixture"""
    conn = MagicMock()
    conn.send_text = MagicMock()
    conn.send_data = MagicMock()
    conn.reboot = MagicMock()
    conn.reset_db = MagicMock()
    conn.get_startup_ts = 1234567890
    conn.get_set_last_position.return_value = (45.0, -90.0)
    conn.interface = MagicMock()
    conn.interface.getLongName.return_value = "TestBot"
    conn.interface.nodes = {}
    conn.node_info.return_value = {
        'user': {'longName': 'TestNode', 'id': '!87654321'}
    }
    return conn


@pytest.fixture
def mock_telegram_connection():
    """Mock Telegram connection fixture"""
    conn = MagicMock()
    conn.send_message = MagicMock()
    return conn


@pytest.fixture
def mock_bot_handler():
    """Mock bot handler fixture"""
    handler = MagicMock()
    handler.get_response.return_value = "Bot response"
    return handler


@pytest.fixture
def meshtastic_bot(mock_database, mock_config, mock_meshtastic_connection,
                  mock_telegram_connection, mock_bot_handler):
    """MeshtasticBot instance fixture"""
    with patch('mtg.output.file.CSVFileWriter') as mock_writer_class:
        with patch('mtg.utils.Memcache'):
            mock_writer = MagicMock()
            mock_writer_class.return_value = mock_writer
            bot = MeshtasticBot(
                mock_database, mock_config, mock_meshtastic_connection,
                mock_telegram_connection, mock_bot_handler
            )
            bot.writer = mock_writer
            return bot


class TestMeshtasticBot:
    """Test MeshtasticBot class"""

    def test_meshtastic_bot_init(self, meshtastic_bot, mock_database, mock_config):
        """Test MeshtasticBot initialization"""
        assert meshtastic_bot.database == mock_database
        assert meshtastic_bot.config == mock_config
        assert meshtastic_bot.filter is None
        assert meshtastic_bot.logger is not None
        assert meshtastic_bot.logger.name == 'Meshtastic Bot'
        assert meshtastic_bot.aprs is None
        assert isinstance(meshtastic_bot.ping_container, dict)

    def test_set_aprs(self, meshtastic_bot):
        """Test set_aprs method"""
        mock_aprs = MagicMock()
        meshtastic_bot.set_aprs(mock_aprs)
        assert meshtastic_bot.aprs == mock_aprs

    def test_set_logger(self, meshtastic_bot):
        """Test set_logger method"""
        mock_logger = MagicMock()
        meshtastic_bot.set_logger(mock_logger)
        assert meshtastic_bot.logger == mock_logger

    def test_set_filter(self, meshtastic_bot):
        """Test set_filter method"""
        mock_filter = MagicMock()
        meshtastic_bot.set_filter(mock_filter)
        assert meshtastic_bot.filter == mock_filter

    def test_subscribe(self, meshtastic_bot):
        """Test subscribe method"""
        with patch('mtg.bot.meshtastic.meshtastic.pub.subscribe') as mock_subscribe:
            meshtastic_bot.subscribe()

            # Should subscribe to 3 topics
            assert mock_subscribe.call_count == 3

            # Check the topics
            call_args = [call[0][1] for call in mock_subscribe.call_args_list]
            assert "meshtastic.receive" in call_args
            assert "meshtastic.connection.established" in call_args
            assert "meshtastic.connection.lost" in call_args

    def test_on_connection(self, meshtastic_bot):
        """Test on_connection method"""
        meshtastic_bot.logger = MagicMock()
        mock_interface = MagicMock()

        meshtastic_bot.on_connection(mock_interface, "test_topic")

        meshtastic_bot.logger.debug.assert_called_once()

    def test_on_node_info(self, meshtastic_bot):
        """Test on_node_info method"""
        meshtastic_bot.logger = MagicMock()
        mock_node = MagicMock()
        mock_interface = MagicMock()

        meshtastic_bot.on_node_info(mock_node, mock_interface)

        meshtastic_bot.logger.debug.assert_called_once()

    def test_process_ping_command(self, meshtastic_bot, mock_meshtastic_connection):
        """Test process_ping_command method"""
        packet = {'fromId': '!12345678'}
        mock_interface = MagicMock()

        with patch('time.time', return_value=1234567890):
            meshtastic_bot.process_ping_command(packet, mock_interface)

        assert '!12345678' in meshtastic_bot.ping_container
        assert meshtastic_bot.ping_container['!12345678']['timestamp'] == 1234567890
        mock_meshtastic_connection.send_data.assert_called_once()

    def test_process_stats_command(self, meshtastic_bot, mock_database, mock_meshtastic_connection):
        """Test process_stats_command method"""
        packet = {'fromId': '!12345678'}
        mock_interface = MagicMock()
        mock_database.get_stats.return_value = "Test stats"

        meshtastic_bot.process_stats_command(packet, mock_interface)

        mock_database.get_stats.assert_called_once_with('!12345678')
        mock_meshtastic_connection.send_text.assert_called_once_with(
            "Test stats", destinationId='!12345678'
        )

    def test_process_distance_command_no_node_info(self, meshtastic_bot, mock_meshtastic_connection):
        """Test process_distance_command with no node info"""
        packet = {'fromId': '!12345678'}
        mock_interface = MagicMock()
        mock_interface.nodes = {}

        meshtastic_bot.process_distance_command(packet, mock_interface)

        mock_meshtastic_connection.send_text.assert_called_once_with(
            "distance err: no node info", destinationId='!12345678'
        )

    def test_process_distance_command_no_position(self, meshtastic_bot, mock_meshtastic_connection):
        """Test process_distance_command with no position"""
        packet = {'fromId': '!12345678'}
        mock_interface = MagicMock()
        mock_interface.nodes = {
            '!12345678': {'user': {'id': '!12345678'}}
        }

        meshtastic_bot.process_distance_command(packet, mock_interface)

        mock_meshtastic_connection.send_text.assert_called_once_with(
            "distance err: no position", destinationId='!12345678'
        )

    def test_process_distance_command_success(self, meshtastic_bot, mock_meshtastic_connection):
        """Test successful process_distance_command"""
        packet = {'fromId': '!12345678'}
        mock_interface = MagicMock()
        mock_interface.nodes = {
            '!12345678': {
                'user': {'id': '!12345678'},
                'position': {'latitude': 45.0, 'longitude': -90.0}
            },
            '!87654321': {
                'user': {'id': '!87654321', 'longName': 'TestNode2'},
                'position': {'latitude': 46.0, 'longitude': -91.0}
            }
        }

        with patch('mtg.geo.get_lat_lon_distance', return_value=100000.5):
            meshtastic_bot.process_distance_command(packet, mock_interface)

        # Should send distance message
        mock_meshtastic_connection.send_text.assert_called()

    @patch('mtg.bot.meshtastic.meshtastic.requests.get')
    def test_get_cur_temp_success(self, mock_get, meshtastic_bot):
        """Test successful weather API call"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'main': {'temp': 20.5, 'pressure': 1013, 'humidity': 65},
            'wind': {'speed': 5.2, 'deg': 180},
            'weather': [{'main': 'Clear'}]
        }
        mock_get.return_value = mock_response

        result = meshtastic_bot.get_cur_temp(45.0, -90.0, "test_key")

        assert "T:20C" in result
        assert "P:1013mb" in result
        assert "H:65%" in result
        assert "W:5m/s" in result

    def test_process_weather_command_no_node_record(self, meshtastic_bot, mock_database,
                                                   mock_meshtastic_connection):
        """Test weather command with no node record"""
        packet = {'fromId': '!12345678'}
        mock_interface = MagicMock()
        mock_database.get_node_record.return_value = (False, None)

        meshtastic_bot.process_weather_command(packet, mock_interface)

        mock_meshtastic_connection.send_text.assert_called_once_with(
            "no information about your node available yet", destinationId='!12345678'
        )

    def test_process_weather_command_no_api_key(self, meshtastic_bot, mock_config,
                                               mock_meshtastic_connection):
        """Test weather command with no API key"""
        packet = {'fromId': '!12345678'}
        mock_interface = MagicMock()
        mock_config.DEFAULT.OpenWeatherKey = ""

        with patch.object(meshtastic_bot, 'config', mock_config):
            meshtastic_bot.process_weather_command(packet, mock_interface)

        mock_meshtastic_connection.send_text.assert_called_once_with(
            "weather command disabled by configuration", destinationId='!12345678'
        )

    def test_process_uptime(self, meshtastic_bot, mock_meshtastic_connection):
        """Test process_uptime method"""
        packet = {'fromId': '!12345678'}
        mock_interface = MagicMock()
        mock_interface.myInfo = MagicMock()
        mock_interface.myInfo.reboot_count = 5
        mock_interface.metadata = MagicMock()
        mock_interface.metadata.firmware_version = "2.1.0"

        with patch('time.time', return_value=1234567900):
            with patch('importlib.metadata.version', return_value="2.0.0"):
                meshtastic_bot.process_uptime(packet, mock_interface)

        mock_meshtastic_connection.send_text.assert_called_once()
        call_args = mock_meshtastic_connection.send_text.call_args
        assert "Bot v" in call_args[0][0]
        assert "FW: v2.1.0" in call_args[0][0]
        assert "Reboots: 5" in call_args[0][0]

    def test_process_pong(self, meshtastic_bot, mock_meshtastic_connection):
        """Test process_pong method"""
        # Setup ping container first
        meshtastic_bot.ping_container['!12345678'] = {'timestamp': 1234567890}

        packet = {
            'fromId': '!12345678',
            'toId': '!87654321',
            'rxTime': 1234567895,
            'rxSnr': -5.2
        }

        mock_meshtastic_connection.node_info.return_value = {
            'user': {'longName': 'TestNode'}
        }

        with patch('time.time', return_value=1234567900):
            meshtastic_bot.process_pong(packet)

        mock_meshtastic_connection.send_text.assert_called_once()
        call_args = mock_meshtastic_connection.send_text.call_args
        assert "Pong from TestNode" in call_args[0][0]
        assert "-5.20 SNR" in call_args[0][0]

    def test_notify_on_new_node_existing_node(self, meshtastic_bot, mock_database):
        """Test notify_on_new_node with existing node"""
        packet = {'fromId': '!12345678'}
        mock_interface = MagicMock()
        mock_database.get_node_record.return_value = (True, MagicMock())

        meshtastic_bot.notify_on_new_node(packet, mock_interface)

        # Should return early, no notification sent
        meshtastic_bot.telegram_connection.send_message.assert_not_called()

    def test_notify_on_new_node_new_node(self, meshtastic_bot, mock_database, mock_config):
        """Test notify_on_new_node with new node"""
        packet = {'fromId': '!12345678'}
        mock_interface = MagicMock()
        mock_interface.nodes = {
            '!12345678': {
                'user': {'longName': 'NewNode'}
            }
        }
        mock_database.get_node_record.return_value = (False, None)

        with patch.object(meshtastic_bot, 'config', mock_config):
            meshtastic_bot.notify_on_new_node(packet, mock_interface)

        # Should send notification
        meshtastic_bot.telegram_connection.send_message_sync.assert_called_once()
        meshtastic_bot.meshtastic_connection.send_text.assert_called_once()

    def test_process_meshtastic_command_weather(self, meshtastic_bot):
        """Test process_meshtastic_command with weather command"""
        packet = {
            'fromId': '!12345678',
            'decoded': {'text': '/w'}
        }
        mock_interface = MagicMock()

        with patch.object(meshtastic_bot, 'process_weather_command') as mock_weather:
            meshtastic_bot.process_meshtastic_command(packet, mock_interface)
            mock_weather.assert_called_once_with(packet, mock_interface)

    def test_process_meshtastic_command_distance(self, meshtastic_bot):
        """Test process_meshtastic_command with distance command"""
        packet = {
            'fromId': '!12345678',
            'decoded': {'text': '/distance'}
        }
        mock_interface = MagicMock()

        with patch.object(meshtastic_bot, 'process_distance_command') as mock_distance:
            meshtastic_bot.process_meshtastic_command(packet, mock_interface)
            mock_distance.assert_called_once_with(packet, mock_interface)

    def test_process_meshtastic_command_unknown(self, meshtastic_bot, mock_meshtastic_connection):
        """Test process_meshtastic_command with unknown command"""
        packet = {
            'fromId': '!12345678',
            'decoded': {'text': '/unknown'}
        }
        mock_interface = MagicMock()

        meshtastic_bot.process_meshtastic_command(packet, mock_interface)

        mock_meshtastic_connection.send_text.assert_called_once_with(
            "unknown command", destinationId='!12345678'
        )

    def test_on_receive_blacklisted_user(self, meshtastic_bot):
        """Test on_receive with blacklisted user"""
        packet = {'fromId': '!12345678', 'toId': '^all'}
        mock_interface = MagicMock()

        mock_filter = MagicMock()
        mock_filter.banned.return_value = True
        meshtastic_bot.filter = mock_filter
        meshtastic_bot.logger = MagicMock()

        meshtastic_bot.on_receive(packet, mock_interface)

        # Should call debug twice (once for receive, once for blacklist)
        assert meshtastic_bot.logger.debug.call_count == 2

    def test_on_receive_hop_limit_exceeded(self, meshtastic_bot, mock_config):
        """Test on_receive with hop limit exceeded"""
        packet = {
            'fromId': '!12345678',
            'toId': '^all',
            'hopLimit': 5,
            'decoded': {'portnum': 'TEXT_MESSAGE_APP', 'text': 'test'}
        }
        mock_interface = MagicMock()
        mock_config.Meshtastic.MaxHopCount = 3
        mock_config.Telegram.NotificationsEnabled = False
        meshtastic_bot.logger = MagicMock()

        with patch.object(meshtastic_bot, 'config', mock_config):
            meshtastic_bot.on_receive(packet, mock_interface)

        # Should call debug twice (once for receive, once for hop limit)
        assert meshtastic_bot.logger.debug.call_count == 2

    def test_on_receive_position_message(self, meshtastic_bot, mock_database, mock_config):
        """Test on_receive with position message"""
        packet = {
            'fromId': '!12345678',
            'toId': '^all',
            'hopLimit': 2,
            'decoded': {'portnum': 'POSITION_APP'}
        }
        mock_interface = MagicMock()
        mock_config.Meshtastic.NodeLogEnabled = True
        mock_config.Telegram.NotificationsEnabled = False
        mock_config.Meshtastic.MaxHopCount = 3

        with patch.object(meshtastic_bot, 'config', mock_config):
            meshtastic_bot.on_receive(packet, mock_interface)

        mock_database.store_location.assert_called_once_with(packet)
        meshtastic_bot.writer.write.assert_called_once_with(packet)

    def test_on_receive_text_message_broadcast(self, meshtastic_bot, mock_database, mock_config):
        """Test on_receive with broadcast text message"""
        packet = {
            'fromId': '!12345678',
            'toId': '^all',
            'hopLimit': 2,
            'decoded': {'portnum': 'TEXT_MESSAGE_APP', 'text': 'Hello mesh!'}
        }
        mock_interface = MagicMock()
        mock_interface.nodes = {
            '!12345678': {
                'user': {'longName': 'TestNode'}
            }
        }
        mock_interface.getLongName.return_value = "BotName"
        mock_config.Telegram.Room = 67890
        mock_config.Telegram.NotificationsEnabled = False

        with patch.object(meshtastic_bot, 'config', mock_config):
            meshtastic_bot.on_receive(packet, mock_interface)

        mock_database.store_message.assert_called_once_with(packet)
        meshtastic_bot.telegram_connection.send_message_sync.assert_called_once_with(
            chat_id=67890, text="TestNode: Hello mesh!"
        )
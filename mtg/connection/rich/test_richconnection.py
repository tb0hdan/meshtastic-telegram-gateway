# -*- coding: utf-8 -*-
# pylint: skip-file
import pytest
import time
import sys
from unittest.mock import MagicMock, patch

# Mock external dependencies to avoid import conflicts
sys.modules['meshtastic'] = MagicMock()
sys.modules['meshtastic.serial_interface'] = MagicMock()
sys.modules['meshtastic.tcp_interface'] = MagicMock()
sys.modules['meshtastic.mesh_pb2'] = MagicMock()
sys.modules['setproctitle'] = MagicMock()

from mtg.connection.rich.richconnection import RichConnection


@pytest.fixture
def mock_logger():
    """Mock logger fixture"""
    return MagicMock()


@pytest.fixture
def mock_config():
    """Mock configuration fixture"""
    config = MagicMock()
    config.enforce_type.side_effect = lambda type_cls, value: type_cls(value) if value else type_cls()
    config.WebApp.Center_Latitude = 45.0
    config.WebApp.Center_Longitude = -90.0
    config.Meshtastic.FIFOEnabled = True
    config.Meshtastic.FIFOPath = '/tmp/test.fifo'
    config.Meshtastic.FIFOCmdPath = '/tmp/test.cmd.fifo'
    return config


@pytest.fixture
def mock_filter():
    """Mock filter fixture"""
    filter_mock = MagicMock()
    filter_mock.banned.return_value = False
    return filter_mock


@pytest.fixture
def mock_database():
    """Mock database fixture"""
    db = MagicMock()
    db.get_last_coordinates.return_value = (45.123, -90.456)
    db.set_coordinates = MagicMock()
    return db


@pytest.fixture
def mock_rg_fn():
    """Mock reverse geocoding function fixture"""
    def rg_func(coords):
        return [{'admin1': 'TestState'}]
    return rg_func


@pytest.fixture
def rich_connection(mock_logger, mock_config, mock_filter, mock_database):
    """RichConnection instance fixture"""
    return RichConnection(
        dev_path="/dev/ttyUSB0",
        logger=mock_logger,
        config=mock_config,
        filter_class=mock_filter,
        database=mock_database,
        startup_ts=1234567890.0
    )


class TestRichConnection:
    """Test RichConnection class"""

    def test_rich_connection_init(self, mock_logger, mock_config, mock_filter, mock_database):
        """Test RichConnection initialization"""
        conn = RichConnection(
            dev_path="/dev/ttyUSB0",
            logger=mock_logger,
            config=mock_config,
            filter_class=mock_filter,
            database=mock_database,
            startup_ts=1234567890.0
        )

        # Check parent class attributes
        assert conn.dev_path == "/dev/ttyUSB0"
        assert conn.logger == mock_logger
        assert conn.config == mock_config
        assert conn.startup_ts == 1234567890.0

        # Check RichConnection specific attributes
        assert conn.database == mock_database
        assert conn.rg_fn is None

    def test_rich_connection_init_with_rg_fn(self, mock_logger, mock_config, mock_filter,
                                           mock_database, mock_rg_fn):
        """Test RichConnection initialization with reverse geocoding function"""
        conn = RichConnection(
            dev_path="/dev/ttyUSB0",
            logger=mock_logger,
            config=mock_config,
            filter_class=mock_filter,
            database=mock_database,
            startup_ts=1234567890.0,
            rg_fn=mock_rg_fn
        )

        assert conn.rg_fn == mock_rg_fn

    def test_get_set_last_position_from_database(self, rich_connection, mock_database):
        """Test get_set_last_position with coordinates from database"""
        mock_database.get_last_coordinates.return_value = (45.123, -90.456)

        lat, lon = rich_connection.get_set_last_position("!12345678")

        assert lat == 45.123
        assert lon == -90.456
        mock_database.get_last_coordinates.assert_called_once_with("!12345678")
        mock_database.set_coordinates.assert_not_called()

    def test_get_set_last_position_runtime_error(self, rich_connection, mock_database, mock_config):
        """Test get_set_last_position when database raises RuntimeError"""
        mock_database.get_last_coordinates.side_effect = RuntimeError("No coordinates")
        mock_config.WebApp.Center_Latitude = 45.0
        mock_config.WebApp.Center_Longitude = -90.0

        with patch('random.randrange', side_effect=[500, 250]):  # Mock random values
            lat, lon = rich_connection.get_set_last_position("!12345678")

            # Should use random coordinates near center
            assert lat == 45.0500  # 45.0 + 500/10000
            assert lon == -89.9750  # -90.0 + 250/10000
            mock_database.set_coordinates.assert_called_once_with("!12345678", lat, lon)

    def test_get_set_last_position_zero_coordinates(self, rich_connection, mock_database, mock_config):
        """Test get_set_last_position with zero coordinates from database"""
        mock_database.get_last_coordinates.return_value = (0.0, 0.0)
        mock_config.WebApp.Center_Latitude = 45.0
        mock_config.WebApp.Center_Longitude = -90.0

        with patch('random.randrange', side_effect=[100, 200]):
            lat, lon = rich_connection.get_set_last_position("!12345678")

            # Should use random coordinates instead of zeros
            assert lat == 45.0100
            assert lon == -89.9800

    def test_get_set_last_position_none_coordinates(self, rich_connection, mock_database, mock_config):
        """Test get_set_last_position with None coordinates from database"""
        mock_database.get_last_coordinates.return_value = (None, None)
        mock_config.WebApp.Center_Latitude = 45.0
        mock_config.WebApp.Center_Longitude = -90.0

        with patch('random.randrange', side_effect=[300, 400]):
            lat, lon = rich_connection.get_set_last_position("!12345678")

            # Should use random coordinates instead of None
            assert lat == 45.0300
            assert lon == -89.9600

    def test_nodes_with_position_property_with_coordinates(self, rich_connection):
        """Test nodes_with_position property with nodes that have coordinates"""
        test_nodes = {
            '!12345678': {
                'user': {'id': '!12345678'},
                'position': {'latitude': 45.123, 'longitude': -90.456}
            },
            '!87654321': {
                'user': {'id': '!87654321'},
                'position': {'latitude': 46.789, 'longitude': -91.012}
            }
        }

        # Mock the interface with nodes
        mock_interface = MagicMock()
        mock_interface.nodes = test_nodes
        rich_connection.interface = mock_interface

        result = rich_connection.nodes_with_position

        assert len(result) == 2
        # The results may be in any order, so check that both latitudes are present
        latitudes = [node['position']['latitude'] for node in result]
        assert 45.123 in latitudes
        assert 46.789 in latitudes

    def test_nodes_with_position_property_without_coordinates(self, rich_connection, mock_logger):
        """Test nodes_with_position property with nodes missing coordinates"""
        test_nodes = {
            '!12345678': {
                'user': {'id': '!12345678'},
                'position': {}  # No coordinates
            }
        }

        # Mock the interface with nodes
        mock_interface = MagicMock()
        mock_interface.nodes = test_nodes
        rich_connection.interface = mock_interface

        with patch.object(rich_connection, 'get_set_last_position', return_value=(45.0, -90.0)):
            result = rich_connection.nodes_with_position

            assert len(result) == 1
            assert result[0]['position']['latitude'] == 45.0
            assert result[0]['position']['longitude'] == -90.0
            assert result[0]['position']['altitude'] == 100
            mock_logger.debug.assert_called_once()

    def test_nodes_with_position_property_no_user_id(self, rich_connection):
        """Test nodes_with_position property with node missing user id"""
        test_nodes = {
            '!12345678': {
                'user': {},  # No id
                'position': {}
            }
        }

        # Mock the interface with nodes
        mock_interface = MagicMock()
        mock_interface.nodes = test_nodes
        rich_connection.interface = mock_interface

        with patch.object(rich_connection, 'get_set_last_position', return_value=(45.0, -90.0)) as mock_get_pos:
            result = rich_connection.nodes_with_position

            # get_set_last_position should be called with None
            mock_get_pos.assert_called_once_with(None)

    def test_nodes_with_position_property_with_rg_function(self, rich_connection, mock_rg_fn):
        """Test nodes_with_position property with reverse geocoding function"""
        rich_connection.rg_fn = mock_rg_fn
        test_nodes = {
            '!12345678': {
                'user': {'id': '!12345678'},
                'position': {'latitude': 45.123, 'longitude': -90.456}
            }
        }

        # Mock the interface with nodes
        mock_interface = MagicMock()
        mock_interface.nodes = test_nodes
        rich_connection.interface = mock_interface

        result = rich_connection.nodes_with_position

        assert len(result) == 1
        assert result[0]['position']['admin1'] == 'TestState'
        # The rg_fn should have been called with the coordinates

    def test_nodes_with_position_property_rg_function_returns_none(self, rich_connection):
        """Test nodes_with_position property when rg_fn returns None"""
        def rg_func_none(coords):
            return None

        rich_connection.rg_fn = rg_func_none
        test_nodes = {
            '!12345678': {
                'user': {'id': '!12345678'},
                'position': {'latitude': 45.123, 'longitude': -90.456}
            }
        }

        # Mock the interface with nodes
        mock_interface = MagicMock()
        mock_interface.nodes = test_nodes
        rich_connection.interface = mock_interface

        result = rich_connection.nodes_with_position

        assert len(result) == 1
        # Should not have admin1 field since rg_fn returned None
        assert 'admin1' not in result[0]['position']

    def test_nodes_with_position_property_rg_function_returns_empty(self, rich_connection):
        """Test nodes_with_position property when rg_fn returns empty list"""
        def rg_func_empty(coords):
            return []

        rich_connection.rg_fn = rg_func_empty
        test_nodes = {
            '!12345678': {
                'user': {'id': '!12345678'},
                'position': {'latitude': 45.123, 'longitude': -90.456}
            }
        }

        # Mock the interface with nodes
        mock_interface = MagicMock()
        mock_interface.nodes = test_nodes
        rich_connection.interface = mock_interface

        result = rich_connection.nodes_with_position

        assert len(result) == 1
        # Should not have admin1 field since rg_fn returned empty list
        assert 'admin1' not in result[0]['position']

    def test_latitude_longitude_i_conversion(self, rich_connection):
        """Test that latitudeI and longitudeI are properly calculated"""
        test_nodes = {
            '!12345678': {
                'user': {'id': '!12345678'},
                'position': {}  # No coordinates, will use generated ones
            }
        }

        # Mock the interface with nodes
        mock_interface = MagicMock()
        mock_interface.nodes = test_nodes
        rich_connection.interface = mock_interface

        with patch.object(rich_connection, 'get_set_last_position', return_value=(45.123456, -90.654321)):
            result = rich_connection.nodes_with_position

            assert len(result) == 1
            position = result[0]['position']
            assert position['latitude'] == 45.123456
            assert position['longitude'] == -90.654321
            # Check that the integer representations are correctly calculated
            assert position['latitudeI'] == '45123456'  # str(45.123456).replace('.', '')[:9]
            assert position['longitudeI'] == '-90654321'  # str(-90.654321).replace('.', '')[:9]

    def test_inheritance_from_meshtastic_connection(self, rich_connection):
        """Test that RichConnection inherits from MeshtasticConnection"""
        from mtg.connection.meshtastic import MeshtasticConnection
        assert isinstance(rich_connection, MeshtasticConnection)

        # Test that parent methods are available
        assert hasattr(rich_connection, 'send_text')
        assert hasattr(rich_connection, 'send_data')
        assert hasattr(rich_connection, 'connect')
        assert hasattr(rich_connection, 'reboot')

    @patch('random.seed')
    def test_random_seed_called(self, mock_seed, mock_logger, mock_config, mock_filter, mock_database):
        """Test that random.seed() is called during initialization"""
        RichConnection(
            dev_path="/dev/ttyUSB0",
            logger=mock_logger,
            config=mock_config,
            filter_class=mock_filter,
            database=mock_database
        )

        mock_seed.assert_called_once()
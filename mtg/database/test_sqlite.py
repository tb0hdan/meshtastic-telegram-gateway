# -*- coding: utf-8 -*-
# pylint: skip-file
import pytest
from unittest.mock import patch, MagicMock, Mock, call
from datetime import datetime, timedelta
from mtg.database.sqlite import MeshtasticDB, sql_debug
import logging
import time


@pytest.fixture
def mock_logger():
    """Set up test fixtures"""
    return MagicMock(spec=logging.Logger)


@pytest.fixture
def test_db_file():
    return "/tmp/test.db"

@patch('mtg.database.sqlite.set_sql_debug')
def test_sql_debug(mock_set_sql_debug):
    """Test sql_debug function"""
    sql_debug()
    mock_set_sql_debug.assert_called_once_with(True)

@patch('mtg.database.sqlite.DB')
def test_meshtastic_db_init(mock_db, test_db_file, mock_logger):
    """Test MeshtasticDB initialization"""
    db = MeshtasticDB(test_db_file, mock_logger)

    mock_db.bind.assert_called_once_with(
        provider='sqlite',
        filename=test_db_file,
        create_db=True
    )
    mock_db.generate_mapping.assert_called_once_with(create_tables=True)
    assert db.logger == mock_logger
    assert db.connection is None

@patch('mtg.database.sqlite.DB')
def test_set_meshtastic(mock_db, test_db_file, mock_logger):
    """Test set_meshtastic method"""
    db = MeshtasticDB(test_db_file, mock_logger)
    mock_connection = MagicMock()

    db.set_meshtastic(mock_connection)

    assert db.connection == mock_connection

@patch('mtg.database.sqlite.DB')
@patch('mtg.database.sqlite.FilterRecord')
def test_get_filter_found(mock_filter_record, mock_db, test_db_file, mock_logger):
    """Test get_filter when filter is found"""
    db = MeshtasticDB(test_db_file, mock_logger)

    mock_record = MagicMock()
    mock_filter_record.select.return_value.first.return_value = mock_record

    found, record = db.get_filter("TestConnection", "test_id")

    assert found is True
    assert record == mock_record
    mock_filter_record.select.assert_called_once()

@patch('mtg.database.sqlite.DB')
@patch('mtg.database.sqlite.FilterRecord')
def test_get_filter_not_found(mock_filter_record, mock_db, test_db_file, mock_logger):
    """Test get_filter when filter is not found"""
    db = MeshtasticDB(test_db_file, mock_logger)

    mock_filter_record.select.return_value.first.return_value = None

    found, record = db.get_filter("TestConnection", "test_id")

    assert found is False
    assert record is None

@patch('mtg.database.sqlite.DB')
@patch('mtg.database.sqlite.MeshtasticNodeRecord')
@patch('mtg.database.sqlite.conditional_log')
def test_get_node_record_new_node(mock_conditional_log, mock_node_record, mock_db, test_db_file, mock_logger):
    """Test get_node_record for new node creation"""
    db = MeshtasticDB(test_db_file, mock_logger)
    mock_connection = MagicMock()
    db.connection = mock_connection

    # Mock existing node not found
    mock_node_record.select.return_value.first.return_value = None

    # Mock connection node info
    test_node_info = {
        'lastHeard': 1640995200,  # Unix timestamp
        'user': {
            'longName': 'Test Node',
            'hwModel': 'ESP32'
        }
    }
    mock_connection.node_info.return_value = test_node_info

    # Mock new node record creation
    mock_new_record = MagicMock()
    mock_node_record.return_value = mock_new_record

    found, record = db.get_node_record("test_node_id")

    assert found is False  # New record created, not found existing
    assert record == mock_new_record
    mock_connection.node_info.assert_called_once_with("test_node_id")

@patch('mtg.database.sqlite.DB')
@patch('mtg.database.sqlite.MeshtasticNodeRecord')
def test_get_node_record_no_connection(mock_node_record, mock_db, test_db_file, mock_logger):
    """Test get_node_record when no connection is set"""
    db = MeshtasticDB(test_db_file, mock_logger)
    db.connection = None

    found, record = db.get_node_record("test_node_id")

    assert found is False
    assert record is None

@patch('mtg.database.sqlite.DB')
@patch('mtg.database.sqlite.MeshtasticNodeRecord')
def test_get_stats(mock_node_record, mock_db):
    """Test get_stats method"""
    mock_node = MagicMock()
    mock_node.locations = [1, 2, 3]  # Mock list with 3 items
    mock_node.messages = [1, 2]     # Mock list with 2 items
    mock_node_record.select.return_value.first.return_value = mock_node

    result = MeshtasticDB.get_stats("test_node_id")

    expected = "Locations: 3. Messages: 2"
    assert result == expected

@patch('mtg.database.sqlite.DB')
@patch('mtg.database.sqlite.MeshtasticNodeRecord')
def test_get_normalized_node_found(mock_node_record, mock_db):
    """Test get_normalized_node when node is found"""
    mock_node1 = MagicMock()
    mock_node1.nodeName = "Test-Node-123"
    mock_node2 = MagicMock()
    mock_node2.nodeName = "Another Node!"

    mock_node_record.select.return_value = [mock_node1, mock_node2]

    # The normalization removes non-alphanumeric chars except hyphens
    # "Test-Node-123" -> "Test-Node-123"
    # So we need to search for "Test-Node-123"
    result = MeshtasticDB.get_normalized_node("Test-Node-123")

    assert result == mock_node1

@patch('mtg.database.sqlite.DB')
@patch('mtg.database.sqlite.MeshtasticNodeRecord')
def test_get_normalized_node_with_special_chars(mock_node_record, mock_db):
    """Test get_normalized_node with special characters that get normalized"""
    mock_node = MagicMock()
    mock_node.nodeName = "Test Node@123!"  # This will normalize to "TestNode123"
    mock_node_record.select.return_value = [mock_node]

    result = MeshtasticDB.get_normalized_node("TestNode123")

    assert result == mock_node

@patch('mtg.database.sqlite.DB')
@patch('mtg.database.sqlite.MeshtasticNodeRecord')
def test_get_normalized_node_not_found(mock_node_record, mock_db):
    """Test get_normalized_node when node is not found"""
    mock_node = MagicMock()
    mock_node.nodeName = "Different-Node"
    mock_node_record.select.return_value = [mock_node]

    result = MeshtasticDB.get_normalized_node("NonExistentNode")

    assert result is None

@patch('mtg.database.sqlite.DB')
@patch('mtg.database.sqlite.MeshtasticMessageRecord')
@patch('time.time')
def test_store_message(mock_time, mock_message_record, mock_db, test_db_file, mock_logger):
    """Test store_message method"""
    mock_time.return_value = 1640995200
    db = MeshtasticDB(test_db_file, mock_logger)

    # Mock get_node_record
    mock_node = MagicMock()
    with patch.object(db, 'get_node_record', return_value=(True, mock_node)):
        packet = {
            'fromId': 'test_node_id',
            'decoded': {
                'text': 'Test message'
            }
        }

        db.store_message(packet)

        mock_message_record.assert_called_once()
        args, kwargs = mock_message_record.call_args
        assert kwargs['message'] == 'Test message'
        assert kwargs['node'] == mock_node

@patch('mtg.database.sqlite.DB')
@patch('mtg.database.sqlite.MeshtasticLocationRecord')
@patch('time.time')
def test_store_location(mock_time, mock_location_record, mock_db, test_db_file, mock_logger):
    """Test store_location method"""
    mock_time.return_value = 1640995200
    db = MeshtasticDB(test_db_file, mock_logger)

    mock_node = MagicMock()
    with patch.object(db, 'get_node_record', return_value=(True, mock_node)):
        packet = {
            'fromId': 'test_node_id',
            'rxSnr': 5.5,
            'decoded': {
                'position': {
                    'altitude': 100.0,
                    'batteryLevel': 85.0,
                    'latitude': 50.4501,
                    'longitude': 30.5234
                }
            }
        }

        db.store_location(packet)

        mock_location_record.assert_called_once()
        args, kwargs = mock_location_record.call_args
        assert kwargs['altitude'] == 100.0
        assert kwargs['batteryLevel'] == 85.0
        assert kwargs['latitude'] == 50.4501
        assert kwargs['longitude'] == 30.5234
        assert kwargs['rxSnr'] == 5.5
        assert kwargs['node'] == mock_node

@patch('mtg.database.sqlite.DB')
def test_store_location_no_from_id(mock_db, test_db_file, mock_logger):
    """Test store_location when fromId is missing"""
    db = MeshtasticDB(test_db_file, mock_logger)

    packet = {'decoded': {'position': {}}}

    # Should return early without doing anything
    db.store_location(packet)

    # No assertions needed - method should return early

@patch('mtg.database.sqlite.DB')
@patch('mtg.database.sqlite.MeshtasticNodeRecord')
def test_get_node_info_found(mock_node_record, mock_db, test_db_file, mock_logger):
    """Test get_node_info when node is found"""
    db = MeshtasticDB(test_db_file, mock_logger)

    mock_node = MagicMock()
    mock_node_record.select.return_value.first.return_value = mock_node

    result = db.get_node_info("test_node_id")

    assert result == mock_node

@patch('mtg.database.sqlite.DB')
@patch('mtg.database.sqlite.MeshtasticNodeRecord')
def test_get_node_info_not_found(mock_node_record, mock_db, test_db_file, mock_logger):
    """Test get_node_info when node is not found"""
    db = MeshtasticDB(test_db_file, mock_logger)

    mock_node_record.select.return_value.first.return_value = None

    with pytest.raises(RuntimeError) as exc_info:
        db.get_node_info("test_node_id")

    assert str(exc_info.value) == "node test_node_id not found"

@patch('mtg.database.sqlite.DB')
@patch('mtg.database.sqlite.MeshtasticNodeRecord')
@patch('mtg.database.sqlite.MeshtasticLocationRecord')
def test_get_last_coordinates_success(mock_location_record, mock_node_record, mock_db, test_db_file, mock_logger):
    """Test get_last_coordinates when coordinates are found"""
    db = MeshtasticDB(test_db_file, mock_logger)

    mock_node = MagicMock()
    mock_node_record.select.return_value.first.return_value = mock_node

    mock_location = MagicMock()
    mock_location.latitude = 50.4501
    mock_location.longitude = 30.5234
    mock_location_record.select.return_value.order_by.return_value.first.return_value = mock_location

    lat, lon = db.get_last_coordinates("test_node_id")

    assert lat == 50.4501
    assert lon == 30.5234

@patch('mtg.database.sqlite.DB')
@patch('mtg.database.sqlite.MeshtasticNodeRecord')
def test_get_last_coordinates_node_not_found(mock_node_record, mock_db, test_db_file, mock_logger):
    """Test get_last_coordinates when node is not found"""
    db = MeshtasticDB(test_db_file, mock_logger)

    mock_node_record.select.return_value.first.return_value = None

    with pytest.raises(RuntimeError) as exc_info:
        db.get_last_coordinates("test_node_id")

    assert str(exc_info.value) == "node test_node_id not found"

@patch('mtg.database.sqlite.DB')
@patch('mtg.database.sqlite.MeshtasticNodeRecord')
@patch('mtg.database.sqlite.MeshtasticLocationRecord')
def test_get_node_track_by_node_id(mock_location_record, mock_node_record, mock_db):
    """Test get_node_track with node ID (starts with !)"""
    mock_node = MagicMock()
    mock_node_record.select.return_value.first.return_value = mock_node

    mock_location1 = MagicMock()
    mock_location1.latitude = 50.0
    mock_location1.longitude = 30.0
    mock_location2 = MagicMock()
    mock_location2.latitude = 51.0
    mock_location2.longitude = 31.0

    mock_location_record.select.return_value.order_by.return_value = [mock_location1, mock_location2]

    result = MeshtasticDB.get_node_track("!test_node_id", tail=3600)

    expected = [
        {"lat": 50.0, "lng": 30.0},
        {"lat": 51.0, "lng": 31.0}
    ]
    assert result == expected

@patch('mtg.database.sqlite.DB')
@patch('mtg.database.sqlite.MeshtasticNodeRecord')
def test_get_node_track_node_not_found(mock_node_record, mock_db):
    """Test get_node_track when node is not found"""
    mock_node_record.select.return_value.first.return_value = None

    result = MeshtasticDB.get_node_track("nonexistent_node")

    assert result == []

@patch('mtg.database.sqlite.DB')
@patch('mtg.database.sqlite.MeshtasticNodeRecord')
@patch('mtg.database.sqlite.MeshtasticLocationRecord')
@patch('time.time')
def test_set_coordinates(mock_time, mock_location_record, mock_node_record, mock_db):
    """Test set_coordinates method"""
    mock_time.return_value = 1640995200

    mock_node = MagicMock()
    mock_node_record.select.return_value.first.return_value = mock_node

    MeshtasticDB.set_coordinates("test_node_id", 50.4501, 30.5234)

    mock_location_record.assert_called_once()
    args, kwargs = mock_location_record.call_args
    assert kwargs['latitude'] == 50.4501
    assert kwargs['longitude'] == 30.5234
    assert kwargs['altitude'] == 0
    assert kwargs['batteryLevel'] == 100
    assert kwargs['rxSnr'] == 0
    assert kwargs['node'] == mock_node

@patch('mtg.database.sqlite.DB')
@patch('mtg.database.sqlite.MeshtasticNodeRecord')
def test_set_coordinates_node_not_found(mock_node_record, mock_db):
    """Test set_coordinates when node is not found"""
    mock_node_record.select.return_value.first.return_value = None

    # Should return early without creating location record
    result = MeshtasticDB.set_coordinates("nonexistent_node", 50.0, 30.0)

    assert result is None
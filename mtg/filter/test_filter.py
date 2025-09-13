# -*- coding: utf-8 -*-
# pylint: skip-file
import pytest
from unittest.mock import MagicMock, Mock
from mtg.filter.filter import Filter, TelegramFilter, MeshtasticFilter, CallSignFilter
import logging


@pytest.fixture
def mock_database():
    return MagicMock()


@pytest.fixture
def mock_config():
    return MagicMock()


@pytest.fixture
def mock_logger():
    return MagicMock(spec=logging.Logger)

def test_filter_init(mock_database, mock_config, mock_logger):
    """Test Filter base class initialization"""
    filter_obj = Filter(mock_database, mock_config, mock_logger)

    assert filter_obj.database == mock_database
    assert filter_obj.config == mock_config
    assert filter_obj.logger == mock_logger
    assert filter_obj.connection_type == ""

def test_filter_banned_not_found(mock_database, mock_config, mock_logger):
    """Test banned method when filter record is not found"""
    filter_obj = Filter(mock_database, mock_config, mock_logger)

    # Mock database returning (False, None) indicating record not found
    mock_database.get_filter.return_value = (False, None)

    result = filter_obj.banned("test_identifier")

    assert result is False
    mock_database.get_filter.assert_called_once_with("", "test_identifier")

def test_filter_banned_found_active(mock_database, mock_config, mock_logger):
    """Test banned method when filter record is found and active"""
    filter_obj = Filter(mock_database, mock_config, mock_logger)

    mock_record = MagicMock()
    mock_record.active = True

    # Mock database returning (True, record) indicating record found
    mock_database.get_filter.return_value = (True, mock_record)

    result = filter_obj.banned("test_identifier")

    assert result is True
    mock_database.get_filter.assert_called_once_with("", "test_identifier")
    mock_logger.error.assert_called_once_with(
        "test_identifier is ban:True for "
    )

def test_filter_banned_found_inactive(mock_database, mock_config, mock_logger):
    """Test banned method when filter record is found but inactive"""
    filter_obj = Filter(mock_database, mock_config, mock_logger)

    mock_record = MagicMock()
    mock_record.active = False

    # Mock database returning (True, record) indicating record found
    mock_database.get_filter.return_value = (True, mock_record)

    result = filter_obj.banned("test_identifier")

    assert result is False
    mock_database.get_filter.assert_called_once_with("", "test_identifier")
    mock_logger.error.assert_called_once_with(
        "test_identifier is ban:False for "
    )

def test_telegram_filter_init(mock_database, mock_config, mock_logger):
    """Test TelegramFilter initialization"""
    filter_obj = TelegramFilter(mock_database, mock_config, mock_logger)

    assert filter_obj.database == mock_database
    assert filter_obj.config == mock_config
    assert filter_obj.logger == mock_logger
    assert filter_obj.connection_type == "Telegram"

def test_telegram_filter_banned(mock_database, mock_config, mock_logger):
    """Test TelegramFilter banned method"""
    filter_obj = TelegramFilter(mock_database, mock_config, mock_logger)

    mock_record = MagicMock()
    mock_record.active = True
    mock_database.get_filter.return_value = (True, mock_record)

    result = filter_obj.banned("telegram_user_123")

    assert result is True
    mock_database.get_filter.assert_called_once_with("Telegram", "telegram_user_123")
    mock_logger.error.assert_called_once_with(
        "telegram_user_123 is ban:True for Telegram"
    )

def test_meshtastic_filter_init(mock_database, mock_config, mock_logger):
    """Test MeshtasticFilter initialization"""
    filter_obj = MeshtasticFilter(mock_database, mock_config, mock_logger)

    assert filter_obj.database == mock_database
    assert filter_obj.config == mock_config
    assert filter_obj.logger == mock_logger
    assert filter_obj.connection_type == "Meshtastic"

def test_meshtastic_filter_banned(mock_database, mock_config, mock_logger):
    """Test MeshtasticFilter banned method"""
    filter_obj = MeshtasticFilter(mock_database, mock_config, mock_logger)

    mock_record = MagicMock()
    mock_record.active = False
    mock_database.get_filter.return_value = (True, mock_record)

    result = filter_obj.banned("!meshtastic_node")

    assert result is False
    mock_database.get_filter.assert_called_once_with("Meshtastic", "!meshtastic_node")
    mock_logger.error.assert_called_once_with(
        "!meshtastic_node is ban:False for Meshtastic"
    )

def test_callsign_filter_init(mock_database, mock_config, mock_logger):
    """Test CallSignFilter initialization"""
    filter_obj = CallSignFilter(mock_database, mock_config, mock_logger)

    assert filter_obj.database == mock_database
    assert filter_obj.config == mock_config
    assert filter_obj.logger == mock_logger
    assert filter_obj.connection_type == "Callsign"

def test_callsign_filter_banned(mock_database, mock_config, mock_logger):
    """Test CallSignFilter banned method"""
    filter_obj = CallSignFilter(mock_database, mock_config, mock_logger)

    mock_database.get_filter.return_value = (False, None)

    result = filter_obj.banned("W1AW")

    assert result is False
    mock_database.get_filter.assert_called_once_with("Callsign", "W1AW")

def test_filter_inheritance(mock_database, mock_config, mock_logger):
    """Test that specialized filters inherit from Filter base class"""
    telegram_filter = TelegramFilter(mock_database, mock_config, mock_logger)
    meshtastic_filter = MeshtasticFilter(mock_database, mock_config, mock_logger)
    callsign_filter = CallSignFilter(mock_database, mock_config, mock_logger)

    assert isinstance(telegram_filter, Filter)
    assert isinstance(meshtastic_filter, Filter)
    assert isinstance(callsign_filter, Filter)

def test_filter_banned_different_identifiers(mock_database, mock_config, mock_logger):
    """Test banned method with different types of identifiers"""
    filter_obj = Filter(mock_database, mock_config, mock_logger)
    mock_database.get_filter.return_value = (False, None)

    # Test with string
    filter_obj.banned("string_id")
    # Test with integer
    filter_obj.banned(12345)
    # Test with None
    filter_obj.banned(None)

    # Should be called 3 times with different identifiers
    assert mock_database.get_filter.call_count == 3

def test_telegram_filter_multiple_calls(mock_database, mock_config, mock_logger):
    """Test TelegramFilter with multiple consecutive calls"""
    filter_obj = TelegramFilter(mock_database, mock_config, mock_logger)

    # First call - banned user
    mock_record1 = MagicMock()
    mock_record1.active = True
    mock_database.get_filter.return_value = (True, mock_record1)

    result1 = filter_obj.banned("banned_user")
    assert result1 is True

    # Second call - allowed user
    mock_database.get_filter.return_value = (False, None)

    result2 = filter_obj.banned("allowed_user")
    assert result2 is False

    # Verify both calls were made
    assert mock_database.get_filter.call_count == 2

def test_filter_logger_message_format(mock_database, mock_config, mock_logger):
    """Test that logger message includes all required information"""
    filter_obj = MeshtasticFilter(mock_database, mock_config, mock_logger)

    mock_record = MagicMock()
    mock_record.active = True
    mock_database.get_filter.return_value = (True, mock_record)

    filter_obj.banned("test_node_id")

    # Check that logger.error was called with the expected format
    expected_message = "test_node_id is ban:True for Meshtastic"
    mock_logger.error.assert_called_once_with(expected_message)

@pytest.mark.parametrize("filter_class,expected_type", [
    (TelegramFilter, "Telegram"),
    (MeshtasticFilter, "Meshtastic"),
    (CallSignFilter, "Callsign")
])
def test_filter_types_have_correct_connection_types(filter_class, expected_type, mock_database, mock_config, mock_logger):
    """Test that each filter type has the correct connection_type"""
    filter_obj = filter_class(mock_database, mock_config, mock_logger)
    assert filter_obj.connection_type == expected_type

@pytest.mark.parametrize("filter_class", [Filter, TelegramFilter, MeshtasticFilter, CallSignFilter])
def test_all_filters_store_constructor_parameters(filter_class, mock_database, mock_config, mock_logger):
    """Test that all filter types correctly store constructor parameters"""
    filter_obj = filter_class(mock_database, mock_config, mock_logger)
    assert filter_obj.database == mock_database
    assert filter_obj.config == mock_config
    assert filter_obj.logger == mock_logger
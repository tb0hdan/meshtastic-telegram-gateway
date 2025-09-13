# -*- coding: utf-8 -*-
# pylint: skip-file
import pytest
from unittest.mock import patch, mock_open, MagicMock
from mtg.config.config import Config
import configparser


@pytest.fixture
def config():
    """Set up test fixtures"""
    return Config("test.ini")

def test_config_init_default_path():
    """Test Config initialization with default path"""
    config = Config()
    assert config.config_path == "mesh.ini"
    assert config.config is None
    assert config.elements == []

def test_config_init_custom_path():
    """Test Config initialization with custom path"""
    config = Config("custom.ini")
    assert config.config_path == "custom.ini"
    assert config.config is None
    assert config.elements == []

@patch('configparser.ConfigParser')
def test_read_config(mock_configparser, config):
    """Test reading configuration file"""
    mock_parser = MagicMock()
    mock_configparser.return_value = mock_parser

    config.read()

    mock_configparser.assert_called_once()
    mock_parser.read.assert_called_once_with("test.ini")
    assert config.config == mock_parser

def test_enforce_type_bool_true():
    """Test type enforcement for boolean true values"""
    result = Config.enforce_type(bool, "true")
    assert result is True

    result = Config.enforce_type(bool, "True")
    assert result is True

    result = Config.enforce_type(bool, "TRUE")
    assert result is True

def test_enforce_type_bool_false():
    """Test type enforcement for boolean false values"""
    result = Config.enforce_type(bool, "false")
    assert result is False

    result = Config.enforce_type(bool, "False")
    assert result is False

    result = Config.enforce_type(bool, "anything_else")
    assert result is False

def test_enforce_type_int():
    """Test type enforcement for integer values"""
    result = Config.enforce_type(int, "42")
    assert result == 42
    assert isinstance(result, int)

def test_enforce_type_float():
    """Test type enforcement for float values"""
    result = Config.enforce_type(float, "3.14")
    assert result == 3.14
    assert isinstance(result, float)

def test_enforce_type_str():
    """Test type enforcement for string values"""
    result = Config.enforce_type(str, "test_string")
    assert result == "test_string"
    assert isinstance(result, str)

def test_getattr_no_config(config):
    """Test __getattr__ when config is None"""
    with pytest.raises(AttributeError, match='config is empty'):
        _ = config.section.key

@patch('configparser.ConfigParser')
def test_getattr_first_level(mock_configparser, config):
    """Test __getattr__ for first level access"""
    mock_parser = MagicMock()
    mock_configparser.return_value = mock_parser
    config.config = mock_parser

    result = config.section

    assert config.elements == ['section']
    assert result == config

@patch('configparser.ConfigParser')
def test_getattr_second_level(mock_configparser, config):
    """Test __getattr__ for second level access"""
    mock_parser = MagicMock()
    mock_parser.__getitem__.return_value = {'key': 'value'}
    mock_configparser.return_value = mock_parser
    config.config = mock_parser

    result = config.section.key

    assert result == 'value'
    assert config.elements == []
    mock_parser.__getitem__.assert_called_with('section')

@patch('configparser.ConfigParser')
def test_getattr_multiple_accesses(mock_configparser, config):
    """Test multiple attribute accesses"""
    mock_parser = MagicMock()
    mock_parser.__getitem__.return_value = {'key1': 'value1', 'key2': 'value2'}
    mock_configparser.return_value = mock_parser
    config.config = mock_parser

    result1 = config.section1.key1
    result2 = config.section2.key2

    assert result1 == 'value1'
    assert result2 == 'value2'
    assert config.elements == []
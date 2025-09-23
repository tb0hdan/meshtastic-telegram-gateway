# -*- coding: utf-8 -*-
# pylint: skip-file
import pytest
from unittest.mock import patch, MagicMock, Mock
import socket
import time

from mtg.connection.mqtt.common import CommonMQTT


class TestCommonMQTT:
    """Test CommonMQTT class"""

    @pytest.fixture
    def common_mqtt(self):
        """Create CommonMQTT instance"""
        return CommonMQTT("Test MQTT")

    def test_init_default(self):
        """Test CommonMQTT initialization with default name"""
        common = CommonMQTT()
        assert common.name == "MQTT Connection"
        assert common.host is None
        assert common.port is None
        assert common.user is None
        assert common.password is None
        assert common.logger is None
        assert common.client is None
        assert common.exit is False

    def test_init_custom_name(self):
        """Test CommonMQTT initialization with custom name"""
        common = CommonMQTT("Custom MQTT")
        assert common.name == "Custom MQTT"
        assert common.exit is False

    def test_set_exit(self, common_mqtt):
        """Test set_exit method"""
        assert common_mqtt.exit is False

        common_mqtt.set_exit(True)
        assert common_mqtt.exit is True

        common_mqtt.set_exit(False)
        assert common_mqtt.exit is False

    def test_set_config(self, common_mqtt):
        """Test set_config method"""
        config = MagicMock()
        config.MQTT.Host = "mqtt.test.com"
        config.MQTT.Port = "8883"
        config.MQTT.User = "testuser"
        config.MQTT.Password = "testpass"

        common_mqtt.set_config(config)

        assert common_mqtt.host == "mqtt.test.com"
        assert common_mqtt.port == 8883
        assert common_mqtt.user == "testuser"
        assert common_mqtt.password == "testpass"

    def test_set_client(self, common_mqtt):
        """Test set_client method"""
        mock_client = MagicMock()

        assert common_mqtt.client is None
        common_mqtt.set_client(mock_client)
        assert common_mqtt.client == mock_client

    def test_set_logger(self, common_mqtt):
        """Test set_logger method"""
        mock_logger = MagicMock()

        assert common_mqtt.logger is None
        common_mqtt.set_logger(mock_logger)
        assert common_mqtt.logger == mock_logger

    @patch('mtg.connection.mqtt.common.setthreadtitle')
    @patch('time.sleep')
    def test_run_loop_successful_connection(self, mock_sleep, mock_setthreadtitle, common_mqtt):
        """Test run_loop with successful connection"""
        mock_client = MagicMock()
        mock_logger = MagicMock()

        common_mqtt.set_client(mock_client)
        common_mqtt.set_logger(mock_logger)
        common_mqtt.host = "localhost"
        common_mqtt.port = 1883

        # Simulate exit after first loop
        mock_client.loop_forever.side_effect = lambda: setattr(common_mqtt, 'exit', True)

        common_mqtt.run_loop()

        mock_setthreadtitle.assert_called_once_with("Test MQTT")
        mock_logger.info.assert_called_once_with("Connecting to localhost:1883...")
        mock_client.connect.assert_called_once_with("localhost", 1883, 60)
        mock_client.loop_forever.assert_called_once()
        mock_sleep.assert_not_called()

    @patch('mtg.connection.mqtt.common.setthreadtitle')
    @patch('time.sleep')
    def test_run_loop_connection_timeout(self, mock_sleep, mock_setthreadtitle, common_mqtt):
        """Test run_loop with connection timeout"""
        mock_client = MagicMock()
        mock_logger = MagicMock()

        common_mqtt.set_client(mock_client)
        common_mqtt.set_logger(mock_logger)
        common_mqtt.host = "localhost"
        common_mqtt.port = 1883

        # Connection times out, then exit on second iteration
        counter = 0
        def connect_side_effect(*args):
            nonlocal counter
            counter += 1
            if counter == 1:
                raise socket.timeout()
            else:
                common_mqtt.exit = True

        mock_client.connect.side_effect = connect_side_effect

        common_mqtt.run_loop()

        mock_logger.error.assert_called_with("Connect timeout...")
        mock_sleep.assert_called_with(10)

    @patch('mtg.connection.mqtt.common.setthreadtitle')
    @patch('time.sleep')
    def test_run_loop_exit_immediately(self, mock_sleep, mock_setthreadtitle, common_mqtt):
        """Test run_loop exits immediately when exit is True"""
        common_mqtt.exit = True
        mock_client = MagicMock()

        common_mqtt.set_client(mock_client)
        common_mqtt.run_loop()

        mock_setthreadtitle.assert_called_once_with("Test MQTT")
        mock_client.connect.assert_not_called()
        mock_client.loop_forever.assert_not_called()
        mock_sleep.assert_not_called()

    @patch('mtg.connection.mqtt.common.setthreadtitle')
    def test_run_loop_without_client(self, mock_setthreadtitle, common_mqtt):
        """Test run_loop without client set"""
        common_mqtt.host = "localhost"
        common_mqtt.port = 1883

        # Exit immediately to avoid infinite loop
        common_mqtt.exit = True
        common_mqtt.run_loop()

        mock_setthreadtitle.assert_called_once_with("Test MQTT")

    def test_run_loop_with_no_logger(self, common_mqtt):
        """Test run_loop without logger (no logging)"""
        mock_client = MagicMock()
        common_mqtt.set_client(mock_client)
        common_mqtt.host = "localhost"
        common_mqtt.port = 1883

        # Simulate connection timeout without logger, exit after one attempt
        def connect_side_effect(*args):
            common_mqtt.exit = True
            raise socket.timeout()

        mock_client.connect.side_effect = connect_side_effect

        with patch('time.sleep') as mock_sleep:
            with patch('mtg.connection.mqtt.common.setthreadtitle'):
                common_mqtt.run_loop()

                mock_sleep.assert_called_with(10)
                # No logger, so no error should be logged
                assert common_mqtt.logger is None
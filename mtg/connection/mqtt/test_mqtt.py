# -*- coding: utf-8 -*-
# pylint: skip-file
import pytest
from unittest.mock import patch, MagicMock, Mock
from threading import Thread

from mtg.connection.mqtt.mqtt import MQTT
from mtg.connection.mqtt.common import CommonMQTT


class TestMQTT:
    """Test MQTT class"""

    @pytest.fixture
    def mock_logger(self):
        """Create mock logger"""
        return MagicMock()

    @pytest.fixture
    def mock_config(self):
        """Create mock configuration"""
        config = MagicMock()
        config.MQTT.Enabled = True
        config.enforce_type.return_value = True
        return config

    @pytest.fixture
    @patch('mtg.connection.mqtt.mqtt.mqtt.Client')
    def mqtt_instance(self, mock_client, mock_logger):
        """Create MQTT instance"""
        return MQTT(
            topic="test/topic",
            host="localhost",
            user="testuser",
            password="testpass",
            logger=mock_logger,
            port=1883
        )

    @patch('mtg.connection.mqtt.mqtt.mqtt.Client')
    def test_init(self, mock_client, mock_logger):
        """Test MQTT initialization"""
        mqtt_instance = MQTT(
            topic="test/topic",
            host="localhost",
            user="testuser",
            password="testpass",
            logger=mock_logger,
            port=1883
        )

        assert mqtt_instance.topic == "test/topic"
        assert mqtt_instance.host == "localhost"
        assert mqtt_instance.port == 1883
        assert mqtt_instance.logger == mock_logger
        assert mqtt_instance.config is None
        assert mqtt_instance.handler is None
        assert mqtt_instance.name == "MQTT Connection"
        assert mqtt_instance.exit is False

        # Check client setup
        mock_client.assert_called_once()
        mock_client.return_value.username_pw_set.assert_called_once_with("testuser", "testpass")

        # Check CommonMQTT setup
        assert isinstance(mqtt_instance.common, CommonMQTT)

    @patch('mtg.connection.mqtt.mqtt.mqtt.Client')
    def test_init_default_port(self, mock_client, mock_logger):
        """Test MQTT initialization with default port"""
        mqtt_instance = MQTT(
            topic="test/topic",
            host="localhost",
            user="testuser",
            password="testpass",
            logger=mock_logger
        )

        assert mqtt_instance.port == 1883

    def test_set_config(self, mqtt_instance, mock_config):
        """Test set_config method"""
        assert mqtt_instance.config is None

        mqtt_instance.set_config(mock_config)

        assert mqtt_instance.config == mock_config
        # Config is set for the mqtt instance

    def test_on_connect(self, mqtt_instance, mock_logger):
        """Test on_connect callback"""
        mock_client = MagicMock()

        mqtt_instance.on_connect(mock_client, None, None, 0)

        mock_logger.info.assert_called_once_with("Connected with result code 0")
        mock_client.subscribe.assert_called_once_with("test/topic/#")

    def test_on_message_with_handler(self, mqtt_instance):
        """Test on_message with handler set"""
        mock_handler = MagicMock()
        mock_msg = MagicMock()
        mock_msg.topic = "test/topic/subtopic"
        mock_msg.payload = b"test payload"

        mqtt_instance.set_handler(mock_handler)
        mqtt_instance.on_message(None, None, mock_msg)

        mock_handler.assert_called_once_with("test/topic/subtopic", b"test payload")

    def test_on_message_without_handler(self, mqtt_instance):
        """Test on_message without handler set"""
        mock_msg = MagicMock()
        mock_msg.topic = "test/topic/subtopic"
        mock_msg.payload = b"test payload"

        # Should not raise exception when handler is None
        mqtt_instance.on_message(None, None, mock_msg)

    def test_on_message_handler_exception(self, mqtt_instance, mock_logger):
        """Test on_message when handler raises exception"""
        mock_handler = MagicMock()
        mock_handler.side_effect = Exception("Handler error")
        mock_msg = MagicMock()
        mock_msg.topic = "test/topic/subtopic"
        mock_msg.payload = b"test payload"

        mqtt_instance.set_handler(mock_handler)
        mqtt_instance.on_message(None, None, mock_msg)

        mock_logger.error.assert_called_once()
        # Verify the error message contains the exception info
        error_call = mock_logger.error.call_args
        assert "Exception('Handler error')" in str(error_call[0][1])

    def test_set_handler(self, mqtt_instance):
        """Test set_handler method"""
        assert mqtt_instance.handler is None

        mock_handler = MagicMock()
        mqtt_instance.set_handler(mock_handler)

        assert mqtt_instance.handler == mock_handler

    def test_shutdown(self, mqtt_instance):
        """Test shutdown method"""
        assert mqtt_instance.exit is False

        mqtt_instance.shutdown()

        mqtt_instance.client.disconnect.assert_called_once()
        assert mqtt_instance.exit is True
        # Should also set exit for common instance
        assert mqtt_instance.common.exit is True

    @patch('mtg.connection.mqtt.mqtt.Thread')
    def test_run_enabled(self, mock_thread, mqtt_instance, mock_config, mock_logger):
        """Test run method when MQTT is enabled"""
        mock_config.enforce_type.return_value = True
        mqtt_instance.set_config(mock_config)

        mqtt_instance.run()

        mock_logger.info.assert_called_once_with("Starting MQTT client...")
        mock_thread.assert_called_once()
        thread_kwargs = mock_thread.call_args[1]
        assert thread_kwargs['target'] == mqtt_instance.common.run_loop
        assert thread_kwargs['daemon'] is True
        assert thread_kwargs['name'] == "MQTT Connection"
        mock_thread.return_value.start.assert_called_once()

    def test_run_disabled(self, mqtt_instance, mock_config, mock_logger):
        """Test run method when MQTT is disabled"""
        mock_config.enforce_type.return_value = False
        mqtt_instance.set_config(mock_config)

        with patch('mtg.connection.mqtt.mqtt.Thread') as mock_thread:
            mqtt_instance.run()

            mock_thread.assert_not_called()
            # Should not log starting message when disabled
            mock_logger.info.assert_not_called()

    def test_run_no_config(self, mqtt_instance, mock_logger):
        """Test run method without config"""
        assert mqtt_instance.config is None

        with patch('mtg.connection.mqtt.mqtt.Thread') as mock_thread:
            mqtt_instance.run()

            mock_thread.assert_not_called()
            mock_logger.info.assert_not_called()

    @patch('mtg.connection.mqtt.mqtt.mqtt.Client')
    def test_client_callbacks_assignment(self, mock_client, mock_logger):
        """Test that client callbacks are properly assigned"""
        mqtt_instance = MQTT(
            topic="test/topic",
            host="localhost",
            user="testuser",
            password="testpass",
            logger=mock_logger
        )

        # Check that callbacks are assigned
        assert mock_client.return_value.on_connect == mqtt_instance.on_connect
        assert mock_client.return_value.on_message == mqtt_instance.on_message

    def test_common_mqtt_integration(self, mqtt_instance, mock_logger):
        """Test integration with CommonMQTT"""
        # Test that CommonMQTT is properly configured
        assert mqtt_instance.common.name == "MQTT Connection"
        assert mqtt_instance.common.client == mqtt_instance.client
        assert mqtt_instance.common.logger == mock_logger

        # Test that common config gets updated
        mock_config = MagicMock()
        mqtt_instance.set_config(mock_config)
        # Config is properly set

    def test_multiple_handlers(self, mqtt_instance):
        """Test replacing handler"""
        handler1 = MagicMock()
        handler2 = MagicMock()

        mqtt_instance.set_handler(handler1)
        assert mqtt_instance.handler == handler1

        mqtt_instance.set_handler(handler2)
        assert mqtt_instance.handler == handler2

        # Test that new handler is called
        mock_msg = MagicMock()
        mock_msg.topic = "test"
        mock_msg.payload = b"test"

        mqtt_instance.on_message(None, None, mock_msg)

        handler1.assert_not_called()
        handler2.assert_called_once_with("test", b"test")

    def test_topic_subscription_format(self, mqtt_instance):
        """Test that topic subscription includes wildcard"""
        mock_client = MagicMock()

        mqtt_instance.on_connect(mock_client, None, None, 0)

        # Should subscribe to topic with wildcard
        mock_client.subscribe.assert_called_once_with("test/topic/#")
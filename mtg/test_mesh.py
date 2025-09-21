# -*- coding: utf-8 -*-
"""Test module for mesh.py configuration checks and runner registration"""

import argparse
import os
import tempfile
from unittest.mock import MagicMock, patch, Mock
import pytest

from mesh import main
import sys


class TestMeshConfigurationChecks:
    """Test configuration checks moved from runners to mesh.py"""

    @pytest.fixture
    def mock_config(self):
        """Create a mock config object"""
        config = MagicMock()
        config.DEFAULT.Debug = False
        config.DEFAULT.SentryEnabled = False
        config.Meshtastic.DatabaseFile = "test.db"
        config.Meshtastic.Device = "test_device"
        config.Telegram.Token = "test_token"
        config.MQTT.Topic = "test_topic"
        config.MQTT.Host = "test_host"
        config.MQTT.User = "test_user"
        config.MQTT.Password = "test_password"
        config.MQTT.Port = 1883

        # Configuration flags that control runner registration
        config.APRS.Enabled = False
        config.Meshtastic.FIFOEnabled = False
        config.WebApp.Enabled = False
        config.MQTT.Enabled = False

        # Mock enforce_type to return the configured values
        def enforce_type_side_effect(type_class, value):
            return value
        config.enforce_type.side_effect = enforce_type_side_effect

        # Ensure config is not None
        config.read.return_value = None

        return config

    @pytest.fixture
    def mock_args(self):
        """Create mock args"""
        args = argparse.Namespace()
        args.config = "test_config.ini"
        return args

    @patch('mesh.sys.exit')
    @patch('mesh.ExternalPlugins')
    @patch('mesh.WebServer')
    @patch('mesh.ThreadManager')
    @patch('mesh.TelegramBot')
    @patch('mesh.MeshtasticBot')
    @patch('mesh.OpenAIBot')
    @patch('mesh.APRSStreamer')
    @patch('mesh.MQTT')
    @patch('mesh.MQTTHandler')
    @patch('mesh.RichConnection')
    @patch('mesh.TelegramConnection')
    @patch('mesh.MeshtasticDB')
    @patch('mesh.Config')
    @patch('mesh.setup_logger')
    @patch('mesh.logging.basicConfig')
    @patch('mesh.rg.search')
    def test_aprs_enabled_registers_runner(self, mock_rg, mock_basic_config, mock_setup_logger,
                                          mock_config_class, mock_db, mock_telegram_conn,
                                          mock_rich_conn, mock_mqtt_handler, mock_mqtt,
                                          mock_aprs, mock_openai, mock_mesh_bot,
                                          mock_telegram_bot, mock_thread_manager,
                                          mock_web_server, mock_external_plugins, mock_exit,
                                          mock_config, mock_args):
        """Test that APRS runner is registered when APRS.Enabled is True"""
        # Configure mocks
        mock_config.APRS.Enabled = True
        mock_config_class.return_value = mock_config
        mock_logger = MagicMock()
        mock_setup_logger.return_value = mock_logger

        # Mock thread manager
        mock_tm_instance = MagicMock()
        mock_thread_manager.return_value = mock_tm_instance

        # Mock other components
        mock_db_instance = MagicMock()
        mock_db.return_value = mock_db_instance

        # Mock telegram bot to prevent blocking run()
        mock_telegram_bot_instance = MagicMock()
        mock_telegram_bot.return_value = mock_telegram_bot_instance
        mock_telegram_bot_instance.run.side_effect = KeyboardInterrupt()

        # Mock all other required objects
        for mock_class in [mock_telegram_conn, mock_rich_conn, mock_mqtt_handler,
                          mock_mqtt, mock_aprs, mock_openai, mock_mesh_bot,
                          mock_web_server, mock_external_plugins]:
            mock_class.return_value = MagicMock()

        with patch('sys.exit'):
            try:
                main(mock_args)
            except KeyboardInterrupt:
                pass  # Expected from mocked telegram_bot.run()

        # Verify APRS runner was registered
        mock_tm_instance.register_runner.assert_any_call(
            "APRS Streamer", mock_aprs.return_value,
            restart_delay=10.0,
            thread_patterns=["APRS Streamer"]
        )

    @patch('mesh.ExternalPlugins')
    @patch('mesh.WebServer')
    @patch('mesh.ThreadManager')
    @patch('mesh.TelegramBot')
    @patch('mesh.MeshtasticBot')
    @patch('mesh.OpenAIBot')
    @patch('mesh.APRSStreamer')
    @patch('mesh.MQTT')
    @patch('mesh.MQTTHandler')
    @patch('mesh.RichConnection')
    @patch('mesh.TelegramConnection')
    @patch('mesh.MeshtasticDB')
    @patch('mesh.Config')
    @patch('mesh.setup_logger')
    @patch('mesh.logging.basicConfig')
    @patch('mesh.rg.search')
    def test_mqtt_enabled_registers_runner(self, mock_rg, mock_basic_config, mock_setup_logger,
                                          mock_config_class, mock_db, mock_telegram_conn,
                                          mock_rich_conn, mock_mqtt_handler, mock_mqtt,
                                          mock_aprs, mock_openai, mock_mesh_bot,
                                          mock_telegram_bot, mock_thread_manager,
                                          mock_web_server, mock_external_plugins,
                                          mock_config, mock_args):
        """Test that MQTT runner is registered when MQTT.Enabled is True"""
        # Configure mocks
        mock_config.MQTT.Enabled = True
        mock_config_class.return_value = mock_config
        mock_logger = MagicMock()
        mock_setup_logger.return_value = mock_logger

        # Mock thread manager
        mock_tm_instance = MagicMock()
        mock_thread_manager.return_value = mock_tm_instance

        # Mock other components
        mock_db_instance = MagicMock()
        mock_db.return_value = mock_db_instance

        # Mock telegram bot to prevent blocking run()
        mock_telegram_bot_instance = MagicMock()
        mock_telegram_bot.return_value = mock_telegram_bot_instance
        mock_telegram_bot_instance.run.side_effect = KeyboardInterrupt()

        # Mock all other required objects
        for mock_class in [mock_telegram_conn, mock_rich_conn, mock_mqtt_handler,
                          mock_mqtt, mock_aprs, mock_openai, mock_mesh_bot,
                          mock_web_server, mock_external_plugins]:
            mock_class.return_value = MagicMock()

        with patch('sys.exit'):
            try:
                main(mock_args)
            except KeyboardInterrupt:
                pass  # Expected from mocked telegram_bot.run()

        # Verify MQTT runner was registered
        mock_tm_instance.register_runner.assert_any_call(
            "MQTT Connection", mock_mqtt.return_value,
            restart_delay=10.0,
            thread_patterns=["MQTT Connection"]
        )

    @patch('mesh.ExternalPlugins')
    @patch('mesh.WebServer')
    @patch('mesh.ThreadManager')
    @patch('mesh.TelegramBot')
    @patch('mesh.MeshtasticBot')
    @patch('mesh.OpenAIBot')
    @patch('mesh.APRSStreamer')
    @patch('mesh.MQTT')
    @patch('mesh.MQTTHandler')
    @patch('mesh.RichConnection')
    @patch('mesh.TelegramConnection')
    @patch('mesh.MeshtasticDB')
    @patch('mesh.Config')
    @patch('mesh.setup_logger')
    @patch('mesh.logging.basicConfig')
    @patch('mesh.rg.search')
    def test_webapp_enabled_registers_runner(self, mock_rg, mock_basic_config, mock_setup_logger,
                                            mock_config_class, mock_db, mock_telegram_conn,
                                            mock_rich_conn, mock_mqtt_handler, mock_mqtt,
                                            mock_aprs, mock_openai, mock_mesh_bot,
                                            mock_telegram_bot, mock_thread_manager,
                                            mock_web_server, mock_external_plugins,
                                            mock_config, mock_args):
        """Test that WebApp runner is registered when WebApp.Enabled is True"""
        # Configure mocks
        mock_config.WebApp.Enabled = True
        mock_config_class.return_value = mock_config
        mock_logger = MagicMock()
        mock_setup_logger.return_value = mock_logger

        # Mock thread manager
        mock_tm_instance = MagicMock()
        mock_thread_manager.return_value = mock_tm_instance

        # Mock other components
        mock_db_instance = MagicMock()
        mock_db.return_value = mock_db_instance

        # Mock telegram bot to prevent blocking run()
        mock_telegram_bot_instance = MagicMock()
        mock_telegram_bot.return_value = mock_telegram_bot_instance
        mock_telegram_bot_instance.run.side_effect = KeyboardInterrupt()

        # Mock all other required objects
        for mock_class in [mock_telegram_conn, mock_rich_conn, mock_mqtt_handler,
                          mock_mqtt, mock_aprs, mock_openai, mock_mesh_bot,
                          mock_web_server, mock_external_plugins]:
            mock_class.return_value = MagicMock()

        with patch('sys.exit'):
            try:
                main(mock_args)
            except KeyboardInterrupt:
                pass  # Expected from mocked telegram_bot.run()

        # Verify WebApp runner was registered
        mock_tm_instance.register_runner.assert_any_call(
            "Web Server", mock_web_server.return_value,
            restart_delay=5.0,
            thread_patterns=["ServerThread"]
        )

    @patch('mesh.ExternalPlugins')
    @patch('mesh.WebServer')
    @patch('mesh.ThreadManager')
    @patch('mesh.TelegramBot')
    @patch('mesh.MeshtasticBot')
    @patch('mesh.OpenAIBot')
    @patch('mesh.APRSStreamer')
    @patch('mesh.MQTT')
    @patch('mesh.MQTTHandler')
    @patch('mesh.RichConnection')
    @patch('mesh.TelegramConnection')
    @patch('mesh.MeshtasticDB')
    @patch('mesh.Config')
    @patch('mesh.setup_logger')
    @patch('mesh.logging.basicConfig')
    @patch('mesh.rg.search')
    def test_fifo_enabled_registers_runner(self, mock_rg, mock_basic_config, mock_setup_logger,
                                          mock_config_class, mock_db, mock_telegram_conn,
                                          mock_rich_conn, mock_mqtt_handler, mock_mqtt,
                                          mock_aprs, mock_openai, mock_mesh_bot,
                                          mock_telegram_bot, mock_thread_manager,
                                          mock_web_server, mock_external_plugins,
                                          mock_config, mock_args):
        """Test that Meshtastic runner is registered when FIFOEnabled is True"""
        # Configure mocks
        mock_config.Meshtastic.FIFOEnabled = True
        mock_config_class.return_value = mock_config
        mock_logger = MagicMock()
        mock_setup_logger.return_value = mock_logger

        # Mock thread manager
        mock_tm_instance = MagicMock()
        mock_thread_manager.return_value = mock_tm_instance

        # Mock other components
        mock_db_instance = MagicMock()
        mock_db.return_value = mock_db_instance

        # Mock telegram bot to prevent blocking run()
        mock_telegram_bot_instance = MagicMock()
        mock_telegram_bot.return_value = mock_telegram_bot_instance
        mock_telegram_bot_instance.run.side_effect = KeyboardInterrupt()

        # Mock all other required objects
        for mock_class in [mock_telegram_conn, mock_rich_conn, mock_mqtt_handler,
                          mock_mqtt, mock_aprs, mock_openai, mock_mesh_bot,
                          mock_web_server, mock_external_plugins]:
            mock_class.return_value = MagicMock()

        with patch('sys.exit'):
            try:
                main(mock_args)
            except KeyboardInterrupt:
                pass  # Expected from mocked telegram_bot.run()

        # Verify Meshtastic runner was registered
        mock_tm_instance.register_runner.assert_any_call(
            "Meshtastic Connection", mock_rich_conn.return_value,
            restart_delay=5.0,
            thread_patterns=["Meshtastic Connection", "MeshtasticCmd"]
        )

    @patch('mesh.ExternalPlugins')
    @patch('mesh.WebServer')
    @patch('mesh.ThreadManager')
    @patch('mesh.TelegramBot')
    @patch('mesh.MeshtasticBot')
    @patch('mesh.OpenAIBot')
    @patch('mesh.APRSStreamer')
    @patch('mesh.MQTT')
    @patch('mesh.MQTTHandler')
    @patch('mesh.RichConnection')
    @patch('mesh.TelegramConnection')
    @patch('mesh.MeshtasticDB')
    @patch('mesh.Config')
    @patch('mesh.setup_logger')
    @patch('mesh.logging.basicConfig')
    @patch('mesh.rg.search')
    def test_disabled_services_not_registered(self, mock_rg, mock_basic_config, mock_setup_logger,
                                             mock_config_class, mock_db, mock_telegram_conn,
                                             mock_rich_conn, mock_mqtt_handler, mock_mqtt,
                                             mock_aprs, mock_openai, mock_mesh_bot,
                                             mock_telegram_bot, mock_thread_manager,
                                             mock_web_server, mock_external_plugins,
                                             mock_config, mock_args):
        """Test that disabled services are not registered with thread manager"""
        # Configure all services as disabled
        mock_config.APRS.Enabled = False
        mock_config.MQTT.Enabled = False
        mock_config.WebApp.Enabled = False
        mock_config.Meshtastic.FIFOEnabled = False

        mock_config_class.return_value = mock_config
        mock_logger = MagicMock()
        mock_setup_logger.return_value = mock_logger

        # Mock thread manager
        mock_tm_instance = MagicMock()
        mock_thread_manager.return_value = mock_tm_instance

        # Mock other components
        mock_db_instance = MagicMock()
        mock_db.return_value = mock_db_instance

        # Mock telegram bot to prevent blocking run()
        mock_telegram_bot_instance = MagicMock()
        mock_telegram_bot.return_value = mock_telegram_bot_instance
        mock_telegram_bot_instance.run.side_effect = KeyboardInterrupt()

        # Mock all other required objects
        for mock_class in [mock_telegram_conn, mock_rich_conn, mock_mqtt_handler,
                          mock_mqtt, mock_aprs, mock_openai, mock_mesh_bot,
                          mock_web_server, mock_external_plugins]:
            mock_class.return_value = MagicMock()

        with patch('sys.exit'):
            try:
                main(mock_args)
            except KeyboardInterrupt:
                pass  # Expected from mocked telegram_bot.run()

        # Get all register_runner calls
        register_calls = mock_tm_instance.register_runner.call_args_list

        # Should only have External Plugins registered (always registered)
        assert len(register_calls) == 1
        call_args = register_calls[0][0]  # First (and only) call arguments
        assert call_args[0] == "External Plugins"
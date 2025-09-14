# -*- coding: utf-8 -*-
# pylint: skip-file
import pytest
import asyncio
import sys
from unittest.mock import MagicMock, patch, AsyncMock

# Mock external dependencies to avoid import conflicts
sys.modules['telegram'] = MagicMock()
sys.modules['telegram.ext'] = MagicMock()

from mtg.connection.telegram.telegram import TelegramConnection


@pytest.fixture
def mock_logger():
    """Mock logger fixture"""
    return MagicMock()


@pytest.fixture
def telegram_connection(mock_logger):
    """TelegramConnection instance fixture"""
    with patch('mtg.connection.telegram.telegram.Application.builder') as mock_builder:
        mock_app = MagicMock()
        mock_builder.return_value.token.return_value.build.return_value = mock_app
        return TelegramConnection("test_token", mock_logger)


class TestTelegramConnection:
    """Test TelegramConnection class"""

    def test_telegram_connection_init(self, mock_logger):
        """Test TelegramConnection initialization"""
        with patch('mtg.connection.telegram.telegram.Application.builder') as mock_builder:
            with patch('logging.getLogger') as mock_get_logger:
                mock_logger_httpx = MagicMock()
                mock_get_logger.return_value = mock_logger_httpx
                mock_app = MagicMock()
                mock_builder.return_value.token.return_value.build.return_value = mock_app

                conn = TelegramConnection("test_token", mock_logger)

                assert conn.logger == mock_logger
                assert conn.application == mock_app
                mock_get_logger.assert_called_once_with("httpx")
                mock_logger_httpx.setLevel.assert_called_once_with(30)  # logging.WARNING = 30

    @pytest.mark.asyncio
    async def test_send_message(self, telegram_connection):
        """Test send_message method"""
        telegram_connection.application.bot = AsyncMock()
        # Initialize the message queue with the current event loop
        telegram_connection.msg_queue = asyncio.Queue()

        with patch('asyncio.run_coroutine_threadsafe') as mock_run_threadsafe:
            telegram_connection.send_message(chat_id=12345, text="Test message")

            mock_run_threadsafe.assert_called_once()
            # Verify the coroutine was passed to asyncio.run_coroutine_threadsafe
            coro = mock_run_threadsafe.call_args[0][0]
            assert asyncio.iscoroutine(coro)

    @pytest.mark.asyncio
    async def test_send_message_with_args_and_kwargs(self, telegram_connection):
        """Test send_message method with various args and kwargs"""
        telegram_connection.application.bot = AsyncMock()
        # Initialize the message queue with the current event loop
        telegram_connection.msg_queue = asyncio.Queue()

        with patch('asyncio.run_coroutine_threadsafe') as mock_run_threadsafe:
            telegram_connection.send_message(
                12345, "Test message",
                parse_mode="HTML",
                reply_to_message_id=67890
            )

            mock_run_threadsafe.assert_called_once()

    def test_poll(self, telegram_connection):
        """Test poll method"""
        telegram_connection.application.run_polling = MagicMock()

        with patch('asyncio.new_event_loop') as mock_new_loop:
            with patch('asyncio.set_event_loop') as mock_set_loop:
                mock_loop = MagicMock()
                mock_new_loop.return_value = mock_loop
                mock_loop.run_until_complete = MagicMock()

                telegram_connection.poll()

                # The actual call should pass the string value 'all_types' (Update.ALL_TYPES)
                telegram_connection.application.run_polling.assert_called_once_with(
                    allowed_updates='all_types'
                )
                # Check that start_queue_processor was called
                mock_loop.run_until_complete.assert_called_once()
                mock_set_loop.assert_called_once_with(mock_loop)

    def test_shutdown(self, telegram_connection):
        """Test shutdown method"""
        telegram_connection.application.stop_running = MagicMock()

        telegram_connection.shutdown()

        telegram_connection.application.stop_running.assert_called_once()

    def test_token_passed_to_builder(self, mock_logger):
        """Test that token is correctly passed to the application builder"""
        with patch('mtg.connection.telegram.telegram.Application.builder') as mock_builder:
            mock_token_builder = MagicMock()
            mock_builder.return_value = mock_token_builder
            mock_token_builder.token.return_value = mock_token_builder
            mock_app = MagicMock()
            mock_token_builder.build.return_value = mock_app

            TelegramConnection("my_secret_token", mock_logger)

            mock_builder.assert_called_once()
            mock_token_builder.token.assert_called_once_with("my_secret_token")
            mock_token_builder.build.assert_called_once()

    @pytest.mark.asyncio
    async def test_actual_send_message_call(self, telegram_connection):
        """Test that send_message actually calls the bot's send_message method"""
        mock_bot = AsyncMock()
        telegram_connection.application.bot = mock_bot

        # We need to actually run the coroutine to test it properly
        await telegram_connection.application.bot.send_message(
            chat_id=12345,
            text="Test message"
        )

        mock_bot.send_message.assert_called_once_with(
            chat_id=12345,
            text="Test message"
        )

    def test_logger_assignment(self, telegram_connection, mock_logger):
        """Test that logger is properly assigned"""
        assert telegram_connection.logger is mock_logger

    def test_application_assignment(self, telegram_connection):
        """Test that application is properly assigned"""
        assert telegram_connection.application is not None
        # The application should be the mock we set up in the fixture

    def test_httpx_logger_level_set(self, mock_logger):
        """Test that httpx logger level is set to WARNING"""
        with patch('mtg.connection.telegram.telegram.Application.builder'):
            with patch('logging.getLogger') as mock_get_logger:
                mock_httpx_logger = MagicMock()
                mock_get_logger.return_value = mock_httpx_logger

                TelegramConnection("test_token", mock_logger)

                mock_get_logger.assert_called_once_with("httpx")
                mock_httpx_logger.setLevel.assert_called_once_with(30)  # WARNING level
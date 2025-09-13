# -*- coding: utf-8 -*-
# pylint: skip-file
import pytest
import asyncio
import tempfile
import os
from unittest.mock import MagicMock, patch, AsyncMock, mock_open

from mtg.bot.telegram.telegram import TelegramBot, check_room


@pytest.fixture
def mock_config():
    """Mock configuration fixture"""
    config = MagicMock()
    config.enforce_type.side_effect = lambda type_cls, value: type_cls(value) if value else type_cls()
    config.Telegram.Room = 12345
    config.Telegram.NotificationsRoom = 67890
    config.Telegram.BotInRooms = False
    config.Telegram.Admin = 11111
    config.Telegram.MapLinkEnabled = True
    config.Telegram.MapLink = "https://example.com/map"
    config.Telegram.NodeIncludeSelf = True
    config.WebApp.ShortenerService = 'none'
    config.WebApp.ExternalURL = 'https://example.com'
    return config


@pytest.fixture
def mock_meshtastic_connection():
    """Mock Meshtastic connection fixture"""
    conn = MagicMock()
    conn.send_text = MagicMock()
    conn.reboot = MagicMock()
    conn.reset_db = MagicMock()
    conn.format_nodes = MagicMock(return_value="Node list")
    conn.get_startup_ts = 1234567890
    conn.interface = MagicMock()
    conn.interface.localNode.getURL.return_value = "https://mesh.local/test"
    conn.interface.getLongName.return_value = "TestBot"
    conn.interface.myInfo = MagicMock()
    conn.interface.myInfo.reboot_count = 5
    conn.interface.metadata = MagicMock()
    conn.interface.metadata.firmware_version = "2.1.0"
    conn.interface.localNode.localConfig.lora.hop_limit = 3
    return conn


@pytest.fixture
def mock_telegram_connection():
    """Mock Telegram connection fixture"""
    conn = MagicMock()
    conn.application = MagicMock()
    conn.poll = MagicMock()
    conn.shutdown = MagicMock()
    return conn


@pytest.fixture
def telegram_bot(mock_config, mock_meshtastic_connection, mock_telegram_connection):
    """TelegramBot instance fixture"""
    return TelegramBot(mock_config, mock_meshtastic_connection, mock_telegram_connection)


class TestCheckRoomDecorator:
    """Test check_room decorator"""

    def test_check_room_not_in_rooms_with_bot_not_in_rooms(self, mock_config):
        """Test decorator when user is not in configured rooms and BotInRooms is False"""
        mock_config.Telegram.BotInRooms = False

        @check_room
        def test_func(bot, update):
            return "success"

        bot = MagicMock()
        bot.config = mock_config
        bot.filter = None

        update = MagicMock()
        update.effective_chat.id = 99999  # Not in rooms

        result = test_func(bot, update)
        assert result == "success"

    def test_check_room_in_rooms_with_bot_not_in_rooms(self, mock_config):
        """Test decorator when user is in configured rooms and BotInRooms is False"""
        mock_config.Telegram.BotInRooms = False

        @check_room
        def test_func(bot, update):
            return "success"

        bot = MagicMock()
        bot.config = mock_config
        bot.filter = None

        update = MagicMock()
        update.effective_chat.id = 12345  # In rooms

        result = test_func(bot, update)
        assert result is None

    def test_check_room_banned_user(self, mock_config):
        """Test decorator with banned user"""
        @check_room
        def test_func(bot, update):
            return "success"

        bot = MagicMock()
        bot.config = mock_config
        bot.filter = MagicMock()
        bot.filter.banned.return_value = True
        bot.logger = MagicMock()

        update = MagicMock()
        update.effective_chat.id = 99999
        update.effective_user.id = 54321

        result = test_func(bot, update)
        assert result is None
        bot.filter.banned.assert_called_once_with('54321')


class TestTelegramBot:
    """Test TelegramBot class"""

    def test_telegram_bot_init(self, telegram_bot, mock_telegram_connection):
        """Test TelegramBot initialization"""
        assert telegram_bot.name == 'Telegram Bot'
        assert telegram_bot.filter is None
        assert telegram_bot.logger is None
        assert telegram_bot.aprs is None

        # Check handlers were added
        app = mock_telegram_connection.application
        assert app.add_handler.call_count == 11

    def test_set_aprs(self, telegram_bot):
        """Test set_aprs method"""
        mock_aprs = MagicMock()
        telegram_bot.set_aprs(mock_aprs)
        assert telegram_bot.aprs == mock_aprs

    def test_set_logger(self, telegram_bot):
        """Test set_logger method"""
        mock_logger = MagicMock()
        telegram_bot.set_logger(mock_logger)
        assert telegram_bot.logger == mock_logger

    def test_set_filter(self, telegram_bot):
        """Test set_filter method"""
        mock_filter = MagicMock()
        telegram_bot.set_filter(mock_filter)
        assert telegram_bot.filter == mock_filter

    def test_shorten_p_no_service(self, telegram_bot):
        """Test URL shortening with no service configured"""
        url = "https://example.com/long/url"
        result = telegram_bot.shorten_p(url)
        assert result == url

    def test_shorten_in_text(self, telegram_bot):
        """Test URL shortening in text"""
        message = "Check this out https://example.com/long more text"
        with patch.object(telegram_bot, 'shorten_p', return_value="https://short.ly/abc"):
            result = telegram_bot.shorten_in_text(message)
            assert result == "Check this out https://short.ly/abc more text"

    def test_shorten_in_text_no_urls(self, telegram_bot):
        """Test URL shortening in text with no URLs"""
        message = "No URLs in this message"
        result = telegram_bot.shorten_in_text(message)
        assert result == message

    @pytest.mark.asyncio
    async def test_start_command(self, telegram_bot, mock_config):
        """Test /start command handler"""
        update = MagicMock()
        update.effective_chat.id = 99999
        update.effective_user.id = 99999

        mock_bot = AsyncMock()
        update.get_bot.return_value = mock_bot

        # Mock the decorator behavior
        with patch.object(telegram_bot, 'config', mock_config):
            with patch.object(telegram_bot, 'filter', None):
                await telegram_bot.start(update, None)

        mock_bot.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_reboot_command_admin(self, telegram_bot, mock_config, mock_meshtastic_connection):
        """Test /reboot command from admin"""
        mock_config.Telegram.Admin = 11111
        update = MagicMock()
        update.effective_chat.id = 11111
        update.effective_user.id = 11111

        mock_bot = AsyncMock()
        update.get_bot.return_value = mock_bot

        with patch.object(telegram_bot, 'config', mock_config):
            with patch.object(telegram_bot, 'filter', None):
                await telegram_bot.reboot(update, None)

        mock_bot.send_message.assert_called_once()
        mock_meshtastic_connection.reboot.assert_called_once()

    @pytest.mark.asyncio
    async def test_reboot_command_non_admin(self, telegram_bot, mock_config, mock_meshtastic_connection):
        """Test /reboot command from non-admin"""
        mock_config.Telegram.Admin = 11111
        telegram_bot.logger = MagicMock()

        update = MagicMock()
        update.effective_chat.id = 22222
        update.effective_user.id = 22222

        with patch.object(telegram_bot, 'config', mock_config):
            with patch.object(telegram_bot, 'filter', None):
                await telegram_bot.reboot(update, None)

        mock_meshtastic_connection.reboot.assert_not_called()
        telegram_bot.logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_qr_code_command(self, telegram_bot, mock_meshtastic_connection):
        """Test /qr command"""
        update = MagicMock()
        update.effective_chat.id = 99999
        update.effective_user.id = 99999

        mock_bot = AsyncMock()
        update.get_bot.return_value = mock_bot

        with patch('tempfile.mkstemp') as mock_mkstemp:
            with patch('pyqrcode.create') as mock_qr:
                with patch('builtins.open', mock_open(read_data="fake image data")):
                    with patch('os.remove'):
                        mock_mkstemp.return_value = (1, '/tmp/test')
                        mock_qr_obj = MagicMock()
                        mock_qr.return_value = mock_qr_obj

                        with patch.object(telegram_bot, 'config', telegram_bot.config):
                            with patch.object(telegram_bot, 'filter', None):
                                await telegram_bot.qr_code(update, None)

        mock_bot.send_photo.assert_called_once()

    @pytest.mark.asyncio
    async def test_echo_wrong_room(self, telegram_bot, mock_config):
        """Test echo handler from wrong room"""
        mock_config.Telegram.Room = 12345
        telegram_bot.logger = MagicMock()

        update = MagicMock()
        update.effective_chat.id = 99999  # Wrong room

        with patch.object(telegram_bot, 'config', mock_config):
            await telegram_bot.echo(update, None)

        telegram_bot.logger.debug.assert_called()

    @pytest.mark.asyncio
    async def test_echo_text_message(self, telegram_bot, mock_config, mock_meshtastic_connection):
        """Test echo handler with text message"""
        mock_config.Telegram.Room = 12345

        update = MagicMock()
        update.effective_chat.id = 12345
        update.effective_user.first_name = "John"
        update.effective_user.last_name = "Doe"
        update.effective_user.id = 54321
        update.message = MagicMock()
        update.message.text = "Hello world"
        update.message.sticker = None
        update.message.photo = None
        update.message.is_topic_message = False
        update.message.reply_to_message = None

        with patch.object(telegram_bot, 'config', mock_config):
            with patch.object(telegram_bot, 'filter', None):
                with patch.object(telegram_bot, 'shorten_in_text', return_value="Hello world"):
                    await telegram_bot.echo(update, None)

        mock_meshtastic_connection.send_text.assert_called_once_with("John Doe: Hello world")

    @pytest.mark.asyncio
    async def test_echo_sticker_message(self, telegram_bot, mock_config, mock_meshtastic_connection):
        """Test echo handler with sticker message"""
        mock_config.Telegram.Room = 12345

        update = MagicMock()
        update.effective_chat.id = 12345
        update.effective_user.first_name = "John"
        update.effective_user.last_name = None
        update.effective_user.id = 54321
        update.message = MagicMock()
        update.message.text = None
        update.message.sticker = MagicMock()
        update.message.sticker.set_name = "funny_stickers"
        update.message.sticker.emoji = "😀"
        update.message.photo = None
        update.message.is_topic_message = False
        update.message.reply_to_message = None

        with patch.object(telegram_bot, 'config', mock_config):
            with patch.object(telegram_bot, 'filter', None):
                await telegram_bot.echo(update, None)

        mock_meshtastic_connection.send_text.assert_called_once_with(
            "John: sent sticker funny_stickers: 😀"
        )

    def test_poll(self, telegram_bot, mock_telegram_connection):
        """Test poll method"""
        telegram_bot.poll()
        mock_telegram_connection.poll.assert_called_once()

    def test_run(self, telegram_bot):
        """Test run method"""
        telegram_bot.run()
        # run() just calls poll(), so we can't test much more without mocking

    def test_shutdown(self, telegram_bot, mock_telegram_connection):
        """Test shutdown method"""
        telegram_bot.shutdown()
        mock_telegram_connection.shutdown.assert_called_once()

    @patch('requests.request')
    def test_shorten_tly_success(self, mock_request, telegram_bot, mock_config):
        """Test successful URL shortening with t.ly"""
        mock_config.WebApp.TLYToken = "test_token"
        mock_response = MagicMock()
        mock_response.json.return_value = {'short_url': 'https://t.ly/abc'}
        mock_request.return_value = mock_response

        result = telegram_bot.shorten_tly("https://example.com/long")

        assert result == 'https://t.ly/abc'
        mock_request.assert_called_once()

    @patch('mtg.bot.telegram.telegram.requests')
    def test_shorten_tly_failure(self, mock_requests, telegram_bot, mock_config):
        """Test failed URL shortening with t.ly"""
        mock_config.WebApp.TLYToken = "test_token"
        telegram_bot.logger = MagicMock()
        # Create a proper RequestException
        mock_requests.RequestException = Exception
        mock_requests.request.side_effect = mock_requests.RequestException("Network error")

        result = telegram_bot.shorten_tly("https://example.com/long")

        assert result == "https://example.com/long"
        telegram_bot.logger.error.assert_called_once()

    @patch('requests.request')
    def test_shorten_pls_success(self, mock_request, telegram_bot, mock_config):
        """Test successful URL shortening with pls.st"""
        mock_config.WebApp.PLSST = "test_token"
        mock_response = MagicMock()
        mock_response.json.return_value = {'short_url': 'https://pls.st/abc'}
        mock_request.return_value = mock_response

        result = telegram_bot.shorten_pls("https://example.com/long")

        assert result == 'https://pls.st/abc'
        mock_request.assert_called_once()

    def test_bg_route_empty_dest(self, telegram_bot):
        """Test bg_route with empty destination"""
        telegram_bot.bg_route("", 3)
        # Should return early, no thread should be started

    @patch('mtg.bot.telegram.telegram.Thread')
    def test_bg_route_valid_dest(self, mock_thread, telegram_bot, mock_meshtastic_connection):
        """Test bg_route with valid destination"""
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        telegram_bot.bg_route("test_dest", 3)

        mock_thread.assert_called_once()
        mock_thread_instance.start.assert_called_once()
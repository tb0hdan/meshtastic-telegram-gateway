"""Tests for validating Telegram configuration handling."""

import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from mtg.bot.telegram.telegram import TelegramBot
from mtg.config import Config


class DummyDispatcher:
    def add_handler(self, *_args, **_kwargs):
        """No-op handler registration used for tests."""


class DummyTelegramConnection:
    def __init__(self):
        self.dispatcher = DummyDispatcher()


def build_config(tmp_path, *, room_value='-100', admin_value='42') -> Config:
    """Create a Config instance backed by a temporary file."""

    config_text = f"""
[Telegram]
Room = {room_value}
NotificationsRoom = -200
Admin = {admin_value}
BotInRooms = true
Token = dummy
MapLinkEnabled = false
NodeIncludeSelf = false
MapLink = https://example.com
"""
    path = tmp_path / 'mesh.ini'
    path.write_text(config_text)
    cfg = Config(str(path))
    cfg.read()
    return cfg


@pytest.fixture()
def meshtastic_connection():
    connection = MagicMock()
    connection.database.iter_pending_links.return_value = []
    return connection


@pytest.fixture()
def telegram_connection():
    return DummyTelegramConnection()


def test_echo_handles_invalid_room_value(caplog, tmp_path, meshtastic_connection, telegram_connection):
    """TelegramBot.echo should not raise when room ID is misconfigured."""

    config = build_config(tmp_path, room_value='invalid')
    logger = logging.getLogger('test-telegram-bot')

    with caplog.at_level(logging.ERROR):
        bot = TelegramBot(config, meshtastic_connection, telegram_connection)
        bot.filter = MagicMock()
        bot.filter.banned.return_value = False
        bot.set_logger(logger)

        update = SimpleNamespace(
            effective_chat=SimpleNamespace(id=12345),
            effective_user=SimpleNamespace(id=67890, first_name='Foo', last_name=None),
            message=None,
        )

        bot.echo(update, MagicMock())

    assert bot._room_id is None
    assert any('Telegram.Room' in record.message for record in caplog.records)


def test_refresh_cached_config_with_valid_values(caplog, tmp_path, meshtastic_connection, telegram_connection):
    """Valid configuration values should be cached without logging errors."""

    config = build_config(tmp_path, room_value='-555', admin_value='99')

    with caplog.at_level(logging.ERROR):
        bot = TelegramBot(config, meshtastic_connection, telegram_connection)

    assert bot._room_id == -555
    assert bot._notifications_room_id == -200
    assert bot._admin_id == 99
    assert bot._bot_in_rooms is True
    assert not caplog.records


def test_echo_ignores_invalid_reply_mapping(
    caplog,
    tmp_path,
    meshtastic_connection,
    telegram_connection,
):
    """Invalid stored reply mappings should not crash the Telegram echo handler."""

    config = build_config(tmp_path, room_value='-555', admin_value='99')
    record = SimpleNamespace(meshtastic_packet_id='not-a-number')
    meshtastic_connection.database.get_link_by_telegram.return_value = record
    meshtastic_connection.database.ensure_message_link.return_value = SimpleNamespace(id=1)
    meshtastic_connection.send_user_text.return_value = [SimpleNamespace(id=42)]
    meshtastic_connection.database.mark_link_sent.return_value = None
    meshtastic_connection.database.add_link_alias.return_value = None

    bot = TelegramBot(config, meshtastic_connection, telegram_connection)
    logger = logging.getLogger('test-telegram-bot')
    bot.set_logger(logger)

    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=-555),
        effective_user=SimpleNamespace(id=67890, first_name='Foo', last_name=None),
        message=SimpleNamespace(
            text='Hello world',
            caption=None,
            sticker=None,
            photo=None,
            message_id=456,
            reply_to_message=SimpleNamespace(
                message_id=123,
                is_topic_message=False,
                forum_topic_created=None,
            ),
            is_topic_message=False,
        ),
    )

    with caplog.at_level(logging.WARNING):
        bot.echo(update, MagicMock())

    assert meshtastic_connection.send_user_text.call_count == 1
    _, kwargs = meshtastic_connection.send_user_text.call_args
    assert kwargs['reply_id'] is None
    assert any('invalid reply mapping' in record.message.lower() for record in caplog.records)


def test_resend_pending_record_marks_invalid_reply_id(
    tmp_path,
    meshtastic_connection,
    telegram_connection,
):
    """Pending records with invalid reply IDs should be marked as failed."""

    config = build_config(tmp_path, room_value='-555', admin_value='99')
    bot = TelegramBot(config, meshtastic_connection, telegram_connection)
    bot.set_logger(logging.getLogger('test-telegram-bot'))

    record = SimpleNamespace(
        id=7,
        reply_to_packet_id='invalid',
        emoji=None,
        sender='Tester',
        payload='Payload',
    )

    bot._resend_pending_record(record)

    meshtastic_connection.send_user_text.assert_not_called()
    meshtastic_connection.send_text.assert_not_called()
    meshtastic_connection.database.mark_link_failed.assert_called_once_with(
        7, 'invalid reply_to_packet_id value'
    )

import logging
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from pony.orm import db_session

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mtg.connection.meshtastic import MeshtasticConnection
from mtg.database import (
    MeshtasticDB,
    MESSAGE_DIRECTION_TELEGRAM_TO_MESH,
)
from mtg.database.sqlite import MessageLinkRecord, MessageLinkAlias


class FakePacket(SimpleNamespace):
    pass


class FakeInterface:
    def __init__(self):
        self.sent_packets = []
        self._next_id = 100

    def sendText(self, text, **_kwargs):  # pylint:disable=invalid-name
        packet = FakePacket(id=self._allocate_id(), text=text, reply_id=None)
        self.sent_packets.append({
            "packet": packet,
            "text": text,
            "reply_id": None,
        })
        return packet

    def _sendPacket(self, mesh_packet, **_kwargs):  # pylint:disable=protected-access,invalid-name
        payload = mesh_packet.decoded.payload.decode("utf-8")
        reply_id = getattr(mesh_packet.decoded, "reply_id", 0) or None
        packet = FakePacket(id=self._allocate_id(), text=payload, reply_id=reply_id)
        self.sent_packets.append({
            "packet": packet,
            "text": payload,
            "reply_id": reply_id,
        })
        return packet

    def _allocate_id(self):
        next_id = self._next_id
        self._next_id += 1
        return next_id


@pytest.fixture(scope="module")
def meshtastic_db(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("db") / "links.sqlite"
    return MeshtasticDB(str(db_path), logging.getLogger("test"))


@pytest.fixture(autouse=True)
def clean_db(meshtastic_db):  # pylint:disable=redefined-outer-name
    with db_session:
        MessageLinkAlias.select().delete(bulk=True)
        MessageLinkRecord.select().delete(bulk=True)
    yield


def test_send_user_text_multipart_chain():
    connection = MeshtasticConnection("test", logging.getLogger("test"), None, None)
    fake_interface = FakeInterface()
    connection.interface = fake_interface

    long_message = "A" * 600
    packets = connection.send_user_text("Tester", long_message, reply_id=None)

    assert len(packets) == len(fake_interface.sent_packets) >= 2
    assert fake_interface.sent_packets[0]["reply_id"] is None
    for idx in range(1, len(fake_interface.sent_packets)):
        prev_packet = fake_interface.sent_packets[idx - 1]["packet"]
        assert fake_interface.sent_packets[idx]["reply_id"] == prev_packet.id


def test_reply_lookup_for_multipart_chain(meshtastic_db):  # pylint:disable=redefined-outer-name
    record = meshtastic_db.ensure_message_link(
        direction=MESSAGE_DIRECTION_TELEGRAM_TO_MESH,
        telegram_chat_id=1,
        telegram_message_id=10,
        payload="hello",
        sender="Alice",
    )
    meshtastic_db.ensure_message_link(
        direction=MESSAGE_DIRECTION_TELEGRAM_TO_MESH,
        telegram_chat_id=1,
        telegram_message_id=10,
        meshtastic_packet_id=201,
    )

    meshtastic_db.add_link_alias(record.id, 201, previous_packet_id=None)
    meshtastic_db.add_link_alias(record.id, 202, previous_packet_id=201)
    meshtastic_db.add_link_alias(record.id, 203, previous_packet_id=202)

    for packet_id in (201, 202, 203):
        linked = meshtastic_db.get_link_by_meshtastic(packet_id)
        assert linked is not None
        with db_session:
            refreshed = MessageLinkRecord[linked.id]
            assert refreshed.telegram_message_id == 10

    with db_session:
        alias = MessageLinkAlias.get(meshtastic_packet_id=202)
        assert alias is not None
        assert alias.previous_packet_id == 201

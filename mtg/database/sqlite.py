# -*- coding: utf-8 -*-
""" SQLite database module """

import logging
import re
import sqlite3
import time
#
from datetime import datetime, timedelta
from typing import (
    AnyStr,
    Iterable,
    Optional as TypingOptional,
)
#
from pony.orm import (
    db_session,
    desc,
    Database,
    Optional,
    PrimaryKey,
    Required,
    Set,
    set_sql_debug,
    select,
)
#
from mtg.log import conditional_log

# has to be global variable ;-(
DB = Database()


MESSAGE_DIRECTION_MESH_TO_TELEGRAM = 'mesh_to_telegram'
MESSAGE_DIRECTION_TELEGRAM_TO_MESH = 'telegram_to_mesh'

MESSAGE_STATUS_PENDING = 'pending'
MESSAGE_STATUS_SENT = 'sent'
MESSAGE_STATUS_FAILED = 'failed'


def sql_debug():
    """
    sql_debug - wrapper to enable debugging
    """
    set_sql_debug(True)


class FirmwareReleaseRecord(DB.Entity):  # pylint:disable=too-few-public-methods
    """
    FirmwareReleaseRecord: firmware release representation in DB
    """
    release = PrimaryKey(str)
    created_at = Required(datetime)
    url = Required(str)
    download_url = Required(str)


class MeshtasticNodeRecord(DB.Entity):  # pylint:disable=too-few-public-methods
    """
    MeshtasticNodeRecord: node record representation in DB
    """
    nodeId = PrimaryKey(str)
    nodeName = Required(str)
    lastHeard = Required(datetime)
    hwModel = Required(str)
    locations = Set(lambda: MeshtasticLocationRecord)
    messages = Set(lambda: MeshtasticMessageRecord)
    # New in 1.1.12
    # shortName = Optional(str)


class MeshtasticLocationRecord(DB.Entity):  # pylint:disable=too-few-public-methods
    """
    MeshtasticLocationRecord: location record representation in DB
    """
    datetime = Required(datetime)
    altitude = Required(float)
    batteryLevel = Required(float)
    latitude = Required(float)
    longitude = Required(float)
    rxSnr = Required(float)
    node = Optional(MeshtasticNodeRecord)
    # New fields in 1.1.12
    # channelUtil = Optional(float)
    # airUtil = Optional(float)


class MeshtasticMessageRecord(DB.Entity):  # pylint:disable=too-few-public-methods
    """
    MeshtasticMessageRecord: message record representation in DB
    """
    datetime = Required(datetime)
    message = Required(str)
    node = Optional(MeshtasticNodeRecord)


class FilterRecord(DB.Entity):
    """
    MeshtasticFilterRecord: filter representation in DB
    """
    # meshtastic, telegram, etc...
    connection = Required(str)
    item = Required(str)
    reason = Required(str)
    active = Required(bool)


class MessageLinkRecord(DB.Entity):  # pylint:disable=too-few-public-methods
    """Persisted mapping between Telegram and Meshtastic messages."""

    id = PrimaryKey(int, auto=True)
    direction = Required(str)
    status = Required(str)
    telegram_chat_id = Optional(int, size=64)
    telegram_message_id = Optional(int, size=64)
    telegram_thread_id = Optional(int, size=64)
    meshtastic_packet_id = Optional(int, size=64)
    payload = Optional(str)
    sender = Optional(str)
    reply_to_packet_id = Optional(int, size=64)
    emoji = Optional(int, size=64)
    retries = Required(int)
    last_error = Optional(str)
    created_at = Required(datetime)
    updated_at = Required(datetime)
    aliases = Set(lambda: MessageLinkAlias)


class MessageLinkAlias(DB.Entity):  # pylint:disable=too-few-public-methods
    """Associates additional Meshtastic packet IDs with a canonical message link."""

    id = PrimaryKey(int, auto=True)
    link = Required(MessageLinkRecord)
    meshtastic_packet_id = Required(int, unique=True, size=64)
    previous_packet_id = Optional(int, size=64)


class MeshtasticDB:
    """
    Meshtastic events database
    """

    def __init__(self, db_file: AnyStr, logger: logging.Logger):
        self.connection = None
        self.logger = logger
        self.db_file = db_file
        if DB.provider is not None:
            DB.disconnect()
            DB.provider = None
            DB.schema = None
        DB.bind(provider='sqlite', filename=db_file, create_db=True)
        migration_state = self._run_migrations(db_file)
        DB.generate_mapping(create_tables=True)
        self._finalize_migrations(db_file, migration_state)

    @staticmethod
    def _run_migrations(db_file: AnyStr) -> dict[str, bool]:
        """Run pre-mapping migrations and return their execution state."""

        migration_state = {
            'message_link_resized': False,
            'message_link_alias_resized': False,
            'message_link_old_table': None,
            'message_link_alias_old_table': None,
        }

        try:
            conn = sqlite3.connect(db_file)
        except sqlite3.Error:
            return migration_state

        with conn:
            table_name, schema_sql = MeshtasticDB._locate_table(
                conn,
                ('MessageLinkRecord', 'message_link_record'),
            )
            if table_name and schema_sql:
                if MeshtasticDB._schema_has_32bit_constraint(
                    schema_sql,
                    (
                        'telegram_chat_id',
                        'telegram_message_id',
                        'telegram_thread_id',
                        'meshtastic_packet_id',
                        'reply_to_packet_id',
                        'emoji',
                    ),
                ):
                    conn.execute('PRAGMA foreign_keys=OFF')
                    old_table_name = f'{table_name}_old'
                    conn.execute(
                        f'ALTER TABLE "{table_name}" RENAME TO "{old_table_name}"',
                    )
                    migration_state['message_link_resized'] = True
                    migration_state['message_link_old_table'] = old_table_name

            table_name, schema_sql = MeshtasticDB._locate_table(
                conn,
                ('MessageLinkAlias', 'message_link_alias'),
            )
            if table_name and schema_sql:
                if MeshtasticDB._schema_has_32bit_constraint(
                    schema_sql,
                    (
                        'meshtastic_packet_id',
                        'previous_packet_id',
                    ),
                ):
                    if not migration_state['message_link_resized']:
                        conn.execute('PRAGMA foreign_keys=OFF')
                    conn.execute('DROP INDEX IF EXISTS idx_MessageLinkAlias__link')
                    conn.execute('DROP INDEX IF EXISTS idx_messagelinkalias__link')
                    old_table_name = f'{table_name}_old'
                    conn.execute(
                        f'ALTER TABLE "{table_name}" RENAME TO "{old_table_name}"',
                    )
                    migration_state['message_link_alias_resized'] = True
                    migration_state['message_link_alias_old_table'] = old_table_name

            if migration_state['message_link_resized'] or migration_state['message_link_alias_resized']:
                conn.execute('PRAGMA foreign_keys=ON')

        conn.close()
        return migration_state

    @staticmethod
    def _schema_has_32bit_constraint(schema_sql: str, columns: Iterable[str]) -> bool:
        """Return True if any of the given columns enforce 32-bit bounds."""

        if not schema_sql:
            return False
        for column in columns:
            constraint_fragment = f'"{column}" BETWEEN -2147483648 AND 2147483647'
            if constraint_fragment in schema_sql:
                return True
        return False

    @staticmethod
    def _finalize_migrations(db_file: AnyStr, migration_state: dict[str, bool]) -> None:
        """Copy data into freshly generated tables after migrations."""

        if not (
            migration_state.get('message_link_resized')
            or migration_state.get('message_link_alias_resized')
        ):
            return

        try:
            conn = sqlite3.connect(db_file)
        except sqlite3.Error:
            return

        try:
            conn.execute('PRAGMA foreign_keys=OFF')
            if migration_state.get('message_link_resized'):
                old_table = migration_state.get('message_link_old_table')
                if old_table:
                    new_table = MeshtasticDB._entity_table_name(
                        MessageLinkRecord,
                        'MessageLinkRecord',
                    )
                    conn.execute(
                        f'''
                        INSERT INTO "{new_table}" (
                            id,
                            direction,
                            status,
                            telegram_chat_id,
                            telegram_message_id,
                            telegram_thread_id,
                            meshtastic_packet_id,
                            payload,
                            sender,
                            reply_to_packet_id,
                            emoji,
                            retries,
                            last_error,
                            created_at,
                            updated_at
                        )
                        SELECT
                            id,
                            direction,
                            status,
                            telegram_chat_id,
                            telegram_message_id,
                            telegram_thread_id,
                            meshtastic_packet_id,
                            COALESCE(payload, ''),
                            COALESCE(sender, ''),
                            reply_to_packet_id,
                            emoji,
                            retries,
                            COALESCE(last_error, ''),
                            created_at,
                            updated_at
                        FROM "{old_table}"
                        ''',
                    )
                    conn.execute(f'DROP TABLE IF EXISTS "{old_table}"')
            if migration_state.get('message_link_alias_resized'):
                old_table = migration_state.get('message_link_alias_old_table')
                if old_table:
                    new_table = MeshtasticDB._entity_table_name(
                        MessageLinkAlias,
                        'MessageLinkAlias',
                    )
                    conn.execute(
                        f'''
                        INSERT INTO "{new_table}" (
                            id,
                            link,
                            meshtastic_packet_id,
                            previous_packet_id
                        )
                        SELECT
                            id,
                            link,
                            meshtastic_packet_id,
                            previous_packet_id
                        FROM "{old_table}"
                        ''',
                    )
                    conn.execute(f'DROP TABLE IF EXISTS "{old_table}"')
            conn.execute('PRAGMA foreign_keys=ON')
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _locate_table(conn: sqlite3.Connection, candidates: Iterable[str]):
        for name in candidates:
            cursor = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                (name,),
            )
            row = cursor.fetchone()
            if row and row[0]:
                return name, row[0]
        return None, None

    @staticmethod
    def _entity_table_name(entity, default_name: str) -> str:
        table = getattr(entity, '_table_', None)
        if table is not None and hasattr(table, 'name'):
            return table.name
        return default_name

    def set_meshtastic(self, connection) -> None:
        """
        set_meshtastic - set meshtastic connection

        :param connection:
        :return:
        """
        self.connection = connection

    @db_session
    def get_filter(self, connection, identifier):
        """
        get_filter - get filter record from DB

        :param connection:
        :param identifier:
        :return:
        """
        if record := FilterRecord.select(
            lambda n: n.connection == connection and n.item == identifier
        ).first():
            return True, record
        return False, None

    @db_session
    def get_node_record(self, node_id: AnyStr):
        """
        get_node_record - get node record from DB

        :param node_id:
        :return:
        """
        node_record = MeshtasticNodeRecord.select(lambda n: n.nodeId == node_id).first()
        node_info = self.connection.node_info(node_id)
        last_heard = datetime.fromtimestamp(node_info.get('lastHeard', 0))
        node_name = node_info.get('user', {}).get('longName', '')
        hw_model = str(node_info.get('user', {}).get('hwModel', ''))
        if not node_record:
            if node_name and hw_model:
                conditional_log(f'creating new record... {node_info}', self.logger, True)
                # create new record
                node_record = MeshtasticNodeRecord(
                    nodeId=node_id,
                    nodeName=node_name,
                    lastHeard=last_heard,
                    hwModel=hw_model,
                )
                return False, node_record
            return False, None
        conditional_log(f'using found record... {node_record}, {node_info}', self.logger, True)
        # Update lastHeard and return record
        node_name = node_name or node_record.nodeName
        node_record.nodeName = node_name or node_id  # pylint:disable=invalid-name
        node_record.lastHeard = last_heard  # pylint:disable=invalid-name
        return True, node_record

    @staticmethod
    @db_session
    def ensure_message_link(
        *,
        direction: str,
        telegram_chat_id: TypingOptional[int] = None,
        telegram_message_id: TypingOptional[int] = None,
        telegram_thread_id: TypingOptional[int] = None,
        meshtastic_packet_id: TypingOptional[int] = None,
        payload: TypingOptional[str] = None,
        sender: TypingOptional[str] = None,
        reply_to_packet_id: TypingOptional[int] = None,
        emoji: TypingOptional[int] = None,
    ) -> MessageLinkRecord:
        """Create or update a message link record."""

        now = datetime.utcnow()
        record = None
        if telegram_chat_id is not None and telegram_message_id is not None:
            record = MessageLinkRecord.get(
                telegram_chat_id=telegram_chat_id,
                telegram_message_id=telegram_message_id,
            )
        if record is None and meshtastic_packet_id is not None:
            record = MessageLinkRecord.get(meshtastic_packet_id=meshtastic_packet_id)
        if record is None:
            record = MessageLinkRecord(
                direction=direction,
                status=MESSAGE_STATUS_PENDING,
                telegram_chat_id=telegram_chat_id,
                telegram_message_id=telegram_message_id,
                telegram_thread_id=telegram_thread_id,
                meshtastic_packet_id=meshtastic_packet_id,
                payload=payload,
                sender=sender,
                reply_to_packet_id=reply_to_packet_id,
                emoji=emoji,
                retries=0,
                created_at=now,
                updated_at=now,
            )
            return record

        # Update existing record with the latest data
        record.direction = direction
        if telegram_chat_id is not None:
            record.telegram_chat_id = telegram_chat_id
        if telegram_message_id is not None:
            record.telegram_message_id = telegram_message_id
        if telegram_thread_id is not None:
            record.telegram_thread_id = telegram_thread_id
        if meshtastic_packet_id is not None:
            record.meshtastic_packet_id = meshtastic_packet_id
        if payload is not None:
            record.payload = payload
        if sender is not None:
            record.sender = sender
        if reply_to_packet_id is not None:
            record.reply_to_packet_id = reply_to_packet_id
        record.emoji = emoji
        record.updated_at = now
        return record

    @staticmethod
    @db_session
    def attach_telegram_metadata(
        record_id: int,
        *,
        telegram_chat_id: int,
        telegram_message_id: int,
        telegram_thread_id: TypingOptional[int] = None,
    ) -> TypingOptional[MessageLinkRecord]:
        """Populate Telegram-specific metadata on an existing message link."""

        record = MessageLinkRecord.get(id=record_id)
        if record is None:
            return None

        record.telegram_chat_id = telegram_chat_id
        record.telegram_message_id = telegram_message_id
        if telegram_thread_id is not None:
            record.telegram_thread_id = telegram_thread_id
        record.updated_at = datetime.utcnow()
        if record.status != MESSAGE_STATUS_SENT:
            record.status = MESSAGE_STATUS_SENT
            record.last_error = ""
            record.retries = 0
        return record

    @staticmethod
    @db_session
    def mark_link_sent(
        record_id: int,
        *,
        telegram_message_id: TypingOptional[int] = None,
        meshtastic_packet_id: TypingOptional[int] = None,
    ) -> None:
        """Mark a message link as successfully sent."""

        record = MessageLinkRecord.get(id=record_id)
        if record is None:
            return
        now = datetime.utcnow()
        record.status = MESSAGE_STATUS_SENT
        record.updated_at = now
        # Pony ORM does not allow assigning ``None`` to optional string
        # attributes once a non-null value has been stored. Clearing the last
        # error by writing ``None`` therefore raises ``ValueError``. Using an
        # empty string conveys the same "no error" meaning without triggering
        # an exception.
        record.last_error = ""
        record.retries = 0
        if telegram_message_id is not None:
            record.telegram_message_id = telegram_message_id
        if meshtastic_packet_id is not None:
            record.meshtastic_packet_id = meshtastic_packet_id

    @staticmethod
    @db_session
    def mark_link_failed(record_id: int, error: str) -> None:
        """Mark a message link as failed permanently."""

        record = MessageLinkRecord.get(id=record_id)
        if record is None:
            return
        record.status = MESSAGE_STATUS_FAILED
        record.last_error = error
        record.updated_at = datetime.utcnow()

    @staticmethod
    @db_session
    def mark_link_retry(record_id: int, error: str) -> None:
        """Record a retry attempt for a message link."""

        record = MessageLinkRecord.get(id=record_id)
        if record is None:
            return
        record.retries += 1
        record.last_error = error
        record.updated_at = datetime.utcnow()

    @staticmethod
    @db_session
    def add_link_alias(
        record_id: int,
        meshtastic_packet_id: int,
        *,
        previous_packet_id: TypingOptional[int] = None,
    ) -> TypingOptional[MessageLinkAlias]:
        """Associate an additional Meshtastic packet ID with an existing link."""

        record = MessageLinkRecord.get(id=record_id)
        if record is None:
            return None
        alias = MessageLinkAlias.get(meshtastic_packet_id=meshtastic_packet_id)
        if alias is None:
            alias = MessageLinkAlias(
                link=record,
                meshtastic_packet_id=meshtastic_packet_id,
                previous_packet_id=previous_packet_id,
            )
        else:
            alias.link = record
            alias.previous_packet_id = previous_packet_id
        return alias

    @staticmethod
    @db_session
    def get_link_by_telegram(chat_id: int, message_id: int) -> TypingOptional[MessageLinkRecord]:
        """Return link record for a Telegram message."""

        return MessageLinkRecord.get(telegram_chat_id=chat_id, telegram_message_id=message_id)

    @staticmethod
    @db_session
    def get_link_by_meshtastic(packet_id: int) -> TypingOptional[MessageLinkRecord]:
        """Return link record for a Meshtastic packet."""

        if record := MessageLinkRecord.get(meshtastic_packet_id=packet_id):
            return record
        alias = MessageLinkAlias.get(meshtastic_packet_id=packet_id)
        if alias:
            return alias.link
        return None

    @staticmethod
    @db_session
    def find_recent_link_by_payload(
        direction: str,
        payload: str,
        *,
        sender: TypingOptional[str] = None,
        max_age: timedelta = timedelta(hours=12),
    ) -> TypingOptional[MessageLinkRecord]:
        """Find the most recent link matching payload (and optionally sender)."""

        cutoff = datetime.utcnow() - max_age
        if sender is not None:
            query = select(
                link for link in MessageLinkRecord
                if link.direction == direction
                and link.sender == sender
                and link.payload == payload
                and link.created_at >= cutoff
            )
        else:
            query = select(
                link for link in MessageLinkRecord
                if link.direction == direction
                and link.payload == payload
                and link.created_at >= cutoff
            )
        return query.order_by(lambda link: desc(link.created_at)).first()

    @staticmethod
    @db_session
    def iter_pending_links(direction: str) -> Iterable[MessageLinkRecord]:
        """Return pending message links for the specified direction."""

        return select(
            link for link in MessageLinkRecord
            if link.direction == direction and link.status == MESSAGE_STATUS_PENDING
        )[:]

    @staticmethod
    @db_session
    def get_stats(node_id: AnyStr) -> AnyStr:
        """
        Get node stats

        :param node_id:
        :return:
        """
        node_record = MeshtasticNodeRecord.select(lambda n: n.nodeId == node_id).first()
        return f"Locations: {len(node_record.locations)}. Messages: {len(node_record.messages)}"

    @staticmethod
    @db_session
    def get_normalized_node(node_name: AnyStr):
        """
        get_normalized_node - get normalized node name
        """
        for node_record in MeshtasticNodeRecord.select():
            normalized = re.sub('[^A-Za-z0-9-]+', '', node_record.nodeName)
            if len(normalized) == 0:
                continue
            if normalized == node_name:
                return node_record
        return None

    @db_session
    def store_message(self, packet: dict) -> None:
        """
        Store Meshtastic message in DB

        :param packet:
        :return:
        """
        from_id = packet.get("fromId")
        _, node_record = self.get_node_record(from_id)
        decoded = packet.get('decoded')
        message = decoded.get('text', '')
        # Save meshtastic message
        MeshtasticMessageRecord(
            datetime=datetime.fromtimestamp(time.time()),
            message=message,
            node=node_record,
        )

    @db_session
    def store_location(self, packet: dict) -> None:
        """
        Store Meshtastic location in DB

        :param packet:
        :return:
        """
        from_id = packet.get("fromId")
        if not from_id:
            return
        _, node_record = self.get_node_record(from_id)
        # Save location
        position = packet.get('decoded', {}).get('position', {})
        # add location to DB
        MeshtasticLocationRecord(
            datetime=datetime.fromtimestamp(time.time()),
            altitude=position.get('altitude', 0),
            batteryLevel=position.get('batteryLevel', 100),
            latitude=position.get('latitude', 0),
            longitude=position.get('longitude', 0),
            rxSnr=packet.get('rxSnr', 0),
            node=node_record,
        )

    @db_session
    def get_node_info(self, node_id: str):
        """
        get_node_info - get node info
        """
        node_record = MeshtasticNodeRecord.select(lambda n: n.nodeId == node_id).first()
        if not node_record:
            raise RuntimeError(f'node {node_id} not found')
        return node_record

    @db_session
    def get_last_coordinates(self, node_id: str):
        """
        get_last_coordinates - get last coordinates for node

        :param node_id:
        :return:
        """
        node_record = MeshtasticNodeRecord.select(lambda n: n.nodeId == node_id).first()
        if not node_record:
            raise RuntimeError(f'node {node_id} not found')
        record = MeshtasticLocationRecord.select(lambda n: n.node == node_record)
        location_record = record.order_by(desc(MeshtasticLocationRecord.datetime)).first()
        if not location_record:
            raise RuntimeError(f'node {node_id} has no stored locations')
        self.logger.debug(location_record)
        return location_record.latitude, location_record.longitude

    @staticmethod
    @db_session
    def get_node_track(node_name, tail=3600):
        """
        get_node_track - get node track

        :param node_name:
        :param tail:
        :return:
        """
        data = []
        if node_name.startswith('!'):
            node_record = MeshtasticNodeRecord.select(lambda n: n.nodeId == node_name).first()
        else:
            node_record = MeshtasticNodeRecord.select(lambda n: n.nodeName == node_name).first()
        if not node_record:
            return data
        # pylint:disable=unnecessary-lambda-assignment
        cnd = lambda n: n.node == node_record and n.datetime >= datetime.now() - timedelta(seconds=tail)
        record = MeshtasticLocationRecord.select(cnd)
        location_record = record.order_by(desc(MeshtasticLocationRecord.datetime))
        data.extend(
            {"lat": l_r.latitude, "lng": l_r.longitude} for l_r in location_record
        )
        return data

    @staticmethod
    @db_session
    def set_coordinates(node_id, lat_r, lon_r) -> None:
        """
        set_coordinates - set node coordinates

        :param self:
        :param node_id:
        :param lat_r:
        :param lon_r:
        :return:
        """
        node_record = MeshtasticNodeRecord.select(lambda n: n.nodeId == node_id).first()
        if not node_record:
            return
        MeshtasticLocationRecord(
            datetime=datetime.fromtimestamp(time.time()),
            altitude=0,
            batteryLevel=100,
            latitude=lat_r,
            longitude=lon_r,
            rxSnr=0,
            node=node_record,
        )
        return

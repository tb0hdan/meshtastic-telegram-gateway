import logging
import time
#
from datetime import datetime
from typing import (
    AnyStr,
)
#
from pony.orm import db_session, desc, Database, Optional, PrimaryKey, Required, Set, set_sql_debug
#
from mtg.connection.meshtastic import MeshtasticConnection
from mtg.log import conditional_log
#

# has to be global variable ;-(
DB = Database()

def sql_debug():
    set_sql_debug(True)

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


class MeshtasticMessageRecord(DB.Entity):  # pylint:disable=too-few-public-methods
    """
    MeshtasticMessageRecord: message record representation in DB
    """
    datetime = Required(datetime)
    message = Required(str)
    node = Optional(MeshtasticNodeRecord)


class MeshtasticFilterRecord(DB.Entity):
    """
    MeshtasticFilterRecord: filter representation in DB
    """
    # meshtastic, telegram, etc...
    connection = Required(str)
    item = Required(str)
    reason = Required(str)
    active = Required(bool)


class MeshtasticDB:
    """
    Meshtastic events database
    """

    def __init__(self, db_file: AnyStr, connection: MeshtasticConnection, logger: logging.Logger):
        self.connection = connection
        self.logger = logger
        DB.bind(provider='sqlite', filename=db_file, create_db=True)
        DB.generate_mapping(create_tables=True)

    @db_session
    def get_node_record(self, node_id: AnyStr) -> MeshtasticNodeRecord:
        """
        Retrieve node record from DB

        :param node_id:
        :return:
        """
        node_record = MeshtasticNodeRecord.select(lambda n: n.nodeId == node_id).first()
        node_info = self.connection.node_info(node_id)
        last_heard = datetime.fromtimestamp(node_info.get('lastHeard', 0))
        if not node_record:
            conditional_log(f'creating new record... {node_info}', self.logger, True)
            # create new record
            node_record = MeshtasticNodeRecord(
                nodeId=node_id,
                nodeName=node_info.get('user', {}).get('longName', ''),
                lastHeard=last_heard,
                hwModel=node_info.get('user', {}).get('hwModel', ''),
            )
            return False, node_record
        conditional_log(f'using found record... {node_record}, {node_info}', self.logger, True)
        # Update lastHeard and return record
        node_record.lastHeard = last_heard  # pylint:disable=invalid-name
        return True, node_record

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
    def get_last_coordinates(self, node_id: str):
        """
        get_last_coordinates - get last known node coordinates
        """
        node_record = MeshtasticNodeRecord.select(lambda n: n.nodeId == node_id).first()
        if not node_record:
            raise RuntimeError(f'node {node_id} not found')
        record = MeshtasticLocationRecord.select(lambda n: n.nodeId == node_id)
        location_record = record.order_by(desc(MeshtasticLocationRecord.datetime)).first()
        if not location_record:
            raise RuntimeError(f'node {node_id} has no stored locations')
        self.logger.debug(location_record)
        return location_record.latitude, location_record.longitude

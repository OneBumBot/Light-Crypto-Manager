"""Diagnostic receiver heartbeat. Never used for admission or control authorization."""
from sqlalchemy import MetaData, Table, Column, String, DateTime, Boolean, func, text
from sqlalchemy.dialects.postgresql import insert

metadata = MetaData()
heartbeats = Table('component_heartbeats', metadata,
    Column('component', String(32), primary_key=True),
    Column('instance', String(64), primary_key=True),
    Column('checked_at', DateTime(timezone=True), nullable=False),
    Column('ready', Boolean, nullable=False))


def receiver_heartbeat(engine, ready):
    import os
    with engine.begin() as c:
        c.execute(text('SET LOCAL statement_timeout = 2000'))
        stmt = insert(heartbeats).values(component='receiver',
            instance=os.environ.get('MQTT_CLIENT_ID', 'lightcrypto-ingestion'),
            checked_at=func.clock_timestamp(), ready=ready)
        c.execute(stmt.on_conflict_do_update(index_elements=['component', 'instance'],
            set_={'checked_at': func.clock_timestamp(), 'ready': ready}))

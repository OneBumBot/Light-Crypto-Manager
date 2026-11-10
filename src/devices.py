"""Non-secret control registry in PostgreSQL; cryptographic keys stay in private files."""
from sqlalchemy import (MetaData, Table, Column, String, Integer, Boolean, CheckConstraint, select)
from sqlalchemy.dialects.postgresql import insert
from src.telemetry import PROFILE, InvalidTelemetry, validate_registry

metadata=MetaData()
devices=Table('telemetry_devices',metadata,
    Column('device_id',String(48),primary_key=True),
    Column('database_device_id',Integer,nullable=False,unique=True),
    Column('topic',String(64),nullable=False,unique=True),
    Column('key_epoch',Integer,nullable=False),
    Column('crypto_profile',String(32),nullable=False),
    Column('enabled',Boolean,nullable=False,server_default='true'),
    CheckConstraint('database_device_id > 0 AND key_epoch > 0',name='ck_devices_numbers'),
    CheckConstraint("topic = 'iot/sensors/' || device_id",name='ck_devices_topic'),
    CheckConstraint("crypto_profile = 'Ascon-AEAD128'",name='ck_devices_profile'))


def provision(connection, registry):
    validate_registry(registry)
    for name,entry in registry.items():
        expected=dict(device_id=name,database_device_id=entry['database_device_id'],
            topic=entry['topic'],key_epoch=entry['key_epoch'],crypto_profile=PROFILE,enabled=True)
        connection.execute(insert(devices).values(**expected).on_conflict_do_nothing())
        existing=connection.execute(select(devices).where(devices.c.device_id==name)).mappings().first()
        if not existing or dict(existing)!=expected:
            raise RuntimeError('Device control registry conflict')


def require_enabled(connection,message,topic):
    row=connection.execute(select(devices).where(devices.c.device_id==message.device_id,
        devices.c.database_device_id==message.database_device_id,devices.c.topic==topic,
        devices.c.key_epoch==message.key_epoch,devices.c.crypto_profile==PROFILE,
        devices.c.enabled.is_(True)).with_for_update(read=True)).first()
    if row is None:
        raise InvalidTelemetry('Device control binding is missing or disabled')
    from src.device_control.server import authorize
    authorize(connection,message)

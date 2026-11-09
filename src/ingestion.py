"""Atomic ingestion: verified packet -> replay/anomaly/outbox in one PG transaction."""
from datetime import datetime, timezone
import os
from sqlalchemy import text, select, func
from src.telemetry import decode_packet, InvalidTelemetry
from src.replay import admit
from src.outbox import enqueue, outbox, record

class IngestionBackpressure(RuntimeError):
    pass

# Quoted names match the unchanged SQLAlchemy models on case-sensitive PostgreSQL.
# Bind parameters keep authenticated device metadata out of the SQL syntax.
FIND_CONFIGURATION = text('''
    SELECT "Device_ID", "Configuration_Update_Date" FROM "Device_Configuration"
    WHERE "Device_ID" = :device_id ORDER BY "Configuration_Update_Date" DESC LIMIT 1
''')
INSERT_ANOMALY = text('''
    INSERT INTO "Anomalies"
        ("Anomaly_Date", "Anomaly_Cause_ID", "Device_ID", "Configuration_Update_Date")
    VALUES (:date, :cause, :device_id, :configuration_date)
''')


def process_packet(packet, registry, engine, topic, now=None):
    message = decode_packet(packet, topic, registry)
    sensor_data = message.sensor
    now = now or datetime.now(timezone.utc)
    delay = (now - datetime.fromisoformat(sensor_data['timestamp'])).total_seconds()
    cause = 0 if sensor_data['temperature'] > 60 or sensor_data['humidity'] > 70 else (1 if delay > 0.5 else None)
    with engine.begin() as connection:
        config = connection.execute(FIND_CONFIGURATION, {'device_id': message.database_device_id}).first()
        if not config:
            raise InvalidTelemetry('Device configuration is missing')
        # Serialize capacity admission only; no network IO inside this lock.
        connection.execute(text('SELECT pg_advisory_xact_lock(734819206)'))
        if not admit(connection, message, 'receiver'):
            record(connection, 'replay', now)
            return None
        if connection.scalar(select(func.count()).select_from(outbox).where(outbox.c.status != 'delivered')) >= int(os.environ.get('MAX_OUTBOX_PENDING', '100000')):
            raise IngestionBackpressure('Outbox capacity reached')
        if cause is not None:
            connection.execute(INSERT_ANOMALY, {
                'date': now.astimezone(timezone.utc).replace(tzinfo=None),
                'cause': cause, 'device_id': config[0], 'configuration_date': config[1],
            })
        enqueue(connection, message, now)
    return sensor_data

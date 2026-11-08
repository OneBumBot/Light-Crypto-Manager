#!/usr/bin/env python3
from src.mqtt_transport import configure_client
"""Legacy MQTT receiver with PostgreSQL anomaly storage (not a broker)."""

import logging
import os
from pathlib import Path
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
from sqlalchemy import create_engine, text

from src.runtime import database_url
from src.telemetry import decode_packet, load_registry, InvalidTelemetry
from src.replay import admit

logger = logging.getLogger(__name__)

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


def set_mqtt_ready(ready):
    path = os.environ.get('MQTT_READY_FILE')
    if path:
        marker = Path(path)
        if ready:
            marker.write_text('subscribed\n')
        else:
            marker.unlink(missing_ok=True)


def on_connect(client, userdata, flags, reason_code, properties):
    set_mqtt_ready(False)
    if reason_code == 0:
        client.subscribe(os.environ.get("MQTT_TOPIC", "iot/sensors/#"), qos=1)
    else:
        logger.error("MQTT connection rejected: %s", reason_code)


def on_subscribe(client, userdata, mid, reason_codes, properties):
    ready = bool(reason_codes) and all(not code.is_failure for code in reason_codes)
    set_mqtt_ready(ready)
    if ready:
        logger.info('MQTT subscription acknowledged')


def on_disconnect(client, userdata, flags, reason_code, properties):
    set_mqtt_ready(False)


def connect_to_db():
    engine = create_engine(database_url(), pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            connection.execute(text('SELECT 1'))
    except Exception:
        engine.dispose()
        raise
    return engine


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
        if not admit(connection, message, 'receiver'):
            return None
        if cause is not None:
            connection.execute(INSERT_ANOMALY, {
                'date': now.astimezone(timezone.utc).replace(tzinfo=None),
                'cause': cause, 'device_id': config[0], 'configuration_date': config[1],
            })
    return sensor_data


def on_message(client, userdata, msg):
    try:
        data = process_packet(msg.payload, userdata['registry'], userdata['engine'], msg.topic)
        logger.info("Telemetry accepted" if data is not None else "Duplicate telemetry ignored")
    except Exception as error:
        # engine.begin rolls back automatically. Never call rollback on a failed
        # global connection or log untrusted payloads / connection credentials.
        logger.error("MQTT packet processing failed (%s)", type(error).__name__)


def main():
    logging.basicConfig(level=logging.INFO)
    set_mqtt_ready(False)
    registry = load_registry()
    engine = connect_to_db()
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                         userdata={"registry": registry, "engine": engine})
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_subscribe = on_subscribe
    client.on_disconnect = on_disconnect
    configure_client(client)
    try:
        client.connect(os.environ.get('MQTT_HOST', 'localhost'),
                       int(os.environ.get('MQTT_PORT', '8883')), 60)
        client.loop_forever()
    except KeyboardInterrupt:
        pass
    finally:
        set_mqtt_ready(False)
        client.disconnect()
        engine.dispose()


if __name__ == '__main__':
    main()

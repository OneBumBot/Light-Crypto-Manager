#!/usr/bin/env python3
"""Legacy MQTT receiver with PostgreSQL anomaly storage (not a broker)."""

import base64
import json
import logging
import os
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
from sqlalchemy import create_engine, text

from src.runtime import ascon_key, database_url
from src.web.ascon.ascon import ascon_decrypt

logger = logging.getLogger(__name__)

# Quoted names match the unchanged SQLAlchemy models on case-sensitive PostgreSQL.
# Bind parameters keep authenticated device metadata out of the SQL syntax.
FIND_CONFIGURATION = text('''
    SELECT "Device_ID", "Configuration_Update_Date"
    FROM "Device_Configuration"
    WHERE "Tag_ID" = (
        SELECT "Tag_ID" FROM "Tag_Journal"
        WHERE starts_with("Tag_Name", :device_id)
        ORDER BY "Creation_Date" DESC, "Tag_ID" DESC LIMIT 1
    )
    ORDER BY "Configuration_Update_Date" DESC, "Device_ID" DESC LIMIT 1
''')
INSERT_ANOMALY = text('''
    INSERT INTO "Anomalies"
        ("Anomaly_Date", "Anomaly_Cause_ID", "Device_ID", "Configuration_Update_Date")
    VALUES (:date, :cause, :device_id, :configuration_date)
''')


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        client.subscribe(os.environ.get("MQTT_TOPIC", "iot/sensors/#"), qos=1)
    else:
        logger.error("MQTT connection rejected: %s", reason_code)


def connect_to_db():
    engine = create_engine(database_url(), pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            connection.execute(text('SELECT 1'))
    except Exception:
        engine.dispose()
        raise
    return engine


def process_packet(packet, key, engine, now=None):
    """Authenticate a legacy packet and record a threshold anomaly atomically.

    Sensor persistence and ML remain separate future work. Existing naive sensor
    timestamps are interpreted as UTC; new publishers send an explicit UTC offset.
    """
    associated_data = base64.b64decode(packet["associated_data"], validate=True)
    plaintext = ascon_decrypt(
        key,
        base64.b64decode(packet["nonce"], validate=True),
        associated_data,
        base64.b64decode(packet["ciphertext"], validate=True),
        packet["algorithm"],
    )
    if plaintext is None:
        raise ValueError("Ascon authentication failed")
    metadata = json.loads(associated_data)
    sensor_data = json.loads(plaintext)
    timestamp = datetime.fromisoformat(metadata["timestamp"])
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    now = now or datetime.now(timezone.utc)
    delay = (now - timestamp).total_seconds()
    cause = None
    if sensor_data['temperature'] > 60 or sensor_data['humidity'] > 70:
        cause = 0
    elif delay > 0.5:
        cause = 1
    if cause is not None:
        with engine.begin() as connection:
            config = connection.execute(
                FIND_CONFIGURATION, {"device_id": metadata["device_id"]}
            ).first()
            if config:
                connection.execute(INSERT_ANOMALY, {
                    "date": now.astimezone(timezone.utc).replace(tzinfo=None),
                    "cause": cause,
                    "device_id": config[0],
                    "configuration_date": config[1],
                })
            else:
                logger.warning("No device configuration matched authenticated metadata")
    return sensor_data


def on_message(client, userdata, msg):
    try:
        data = process_packet(json.loads(msg.payload), userdata['key'], userdata['engine'])
        logger.info("Received sensor data on %s: temperature=%s humidity=%s",
                    msg.topic, data['temperature'], data['humidity'])
    except Exception as error:
        # engine.begin rolls back automatically. Never call rollback on a failed
        # global connection or log untrusted payloads / connection credentials.
        logger.error("MQTT packet processing failed (%s)", type(error).__name__)


def main():
    logging.basicConfig(level=logging.INFO)
    key = ascon_key()
    engine = connect_to_db()
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                         userdata={"key": key, "engine": engine})
    client.on_connect = on_connect
    client.on_message = on_message
    if os.environ.get('MQTT_USERNAME'):
        client.username_pw_set(os.environ['MQTT_USERNAME'], os.environ.get('MQTT_PASSWORD', ''))
    try:
        client.connect(os.environ.get('MQTT_HOST', 'localhost'),
                       int(os.environ.get('MQTT_PORT', '1883')), 60)
        client.loop_forever()
    except KeyboardInterrupt:
        pass
    finally:
        client.disconnect()
        engine.dispose()


if __name__ == '__main__':
    main()

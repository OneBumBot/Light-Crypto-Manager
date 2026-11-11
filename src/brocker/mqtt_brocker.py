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

from src.ingestion import process_packet

def set_mqtt_ready(ready):
    path = os.environ.get('MQTT_READY_FILE')
    if path:
        marker = Path(path)
        if ready:
            marker.write_text('subscribed\n')
        else:
            marker.unlink(missing_ok=True)


def on_connect(client, userdata, flags, reason_code, properties):
    if userdata is not None: userdata['subscribed'] = False
    set_mqtt_ready(False)
    if reason_code == 0:
        client.subscribe(os.environ.get("MQTT_TOPIC", "iot/sensors/#"), qos=1)
    else:
        logger.error("MQTT connection rejected: %s", reason_code)


def on_subscribe(client, userdata, mid, reason_codes, properties):
    ready = bool(reason_codes) and all(not code.is_failure for code in reason_codes)
    if userdata is not None: userdata['subscribed'] = ready
    set_mqtt_ready(ready)
    if ready:
        logger.info('MQTT subscription acknowledged')


def on_disconnect(client, userdata, flags, reason_code, properties):
    if userdata is not None: userdata['subscribed'] = False
    set_mqtt_ready(False)


def connect_to_db():
    engine = create_engine(database_url(), pool_pre_ping=True, connect_args={'connect_timeout': 3})
    try:
        with engine.connect() as connection:
            connection.execute(text('SELECT 1'))
    except Exception:
        engine.dispose()
        raise
    return engine



def on_message(client, userdata, msg):
    from src.outbox import record
    try:
        with userdata['engine'].begin() as connection:
            record(connection, 'incoming')
        data = process_packet(msg.payload, userdata['registry'], userdata['engine'], msg.topic)
        logger.info("Telemetry accepted" if data is not None else "Duplicate telemetry ignored")
    except InvalidTelemetry:
        try:
            with userdata['engine'].begin() as connection:
                record(connection, 'rejected')
                from src.security_events import capture
                capture(connection, 'rejected')
        except Exception:
            if client is not None: client.disconnect()
            return
        logger.warning('Invalid telemetry rejected')
    except Exception as error:
        logger.error("MQTT packet processing failed (%s)", type(error).__name__)
        # Keep QoS1 packet unacknowledged. Persistent session redelivers on reconnect.
        if client is not None:
            client.disconnect()
        return
    if client is not None and msg.qos == 1:
        client.ack(msg.mid, msg.qos)


def main():
    logging.basicConfig(level=logging.INFO)
    set_mqtt_ready(False)
    registry = load_registry()
    engine = connect_to_db()
    import signal
    from threading import Event, Thread
    stop = Event()
    context = {"registry": registry, "engine": engine, "subscribed": False}
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                         client_id=os.environ.get('MQTT_CLIENT_ID','lightcrypto-ingestion'),
                         clean_session=False, manual_ack=True,
                         userdata=context)
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_subscribe = on_subscribe
    client.on_disconnect = on_disconnect
    client.reconnect_delay_set(min_delay=1, max_delay=30)
    configure_client(client)
    def report_status():
        from sqlalchemy.exc import SQLAlchemyError
        from src.system_status import receiver_heartbeat
        while not stop.is_set():
            try:
                receiver_heartbeat(engine, bool(context['subscribed'] and client.is_connected()))
            except SQLAlchemyError:
                logger.warning('Receiver diagnostic heartbeat unavailable')
            stop.wait(2)
    reporter = Thread(target=report_status, daemon=True)
    reporter.start()
    def shutdown(*_):
        stop.set()
        client.disconnect()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, shutdown)
    try:
        while not stop.is_set():
            try:
                client.connect(os.environ.get('MQTT_HOST', 'localhost'),
                               int(os.environ.get('MQTT_PORT', '8883')), 60)
                client.loop_forever(retry_first_connection=True)
            except (OSError, RuntimeError) as error:
                logger.error('MQTT connection failed (%s)', type(error).__name__)
            if not stop.is_set():
                stop.wait(2)
    finally:
        stop.set()
        reporter.join(timeout=4)
        set_mqtt_ready(False)
        client.disconnect()
        engine.dispose()


if __name__ == '__main__':
    main()

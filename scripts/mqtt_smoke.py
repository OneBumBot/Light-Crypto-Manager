"""Check the live broker/receiver/DB path using isolated temporary device rows."""

import argparse
import base64
from datetime import datetime, timezone
import json
import os
import threading
import time
import uuid

import paho.mqtt.client as mqtt
from sqlalchemy import create_engine, text

from src.runtime import ascon_key, database_url


def wait_for(predicate, message, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.1)
    raise TimeoutError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expect-demo', action='store_true')
    args = parser.parse_args()
    device = 'smoke-' + uuid.uuid4().hex[:20]
    topic = 'iot/sensors/' + device
    identity = int(uuid.uuid4().hex[:7], 16) + 1000000
    date = datetime.now(timezone.utc).replace(tzinfo=None)
    os.environ['MQTT_CLIENT_ID'] = device
    # Load the real publisher helpers with this run's isolated device identity.
    from src.publisher.mqtt_pub import decrypt_data, encrypt_data

    key = ascon_key()
    engine = create_engine(database_url(), pool_pre_ping=True)
    subscribed, demo_received = threading.Event(), threading.Event()
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=device)
    if os.environ.get('MQTT_USERNAME'):
        client.username_pw_set(os.environ['MQTT_USERNAME'], os.environ.get('MQTT_PASSWORD', ''))

    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            client.subscribe('iot/sensors/device1' if args.expect_demo else topic, qos=1)

    def on_subscribe(client, userdata, mid, reason_codes, properties):
        if reason_codes and all(not code.is_failure for code in reason_codes):
            subscribed.set()

    def on_message(client, userdata, msg):
        if args.expect_demo and msg.topic == 'iot/sensors/device1':
            try:
                data = json.loads(decrypt_data(json.loads(msg.payload), key))
                if isinstance(data['temperature'], (float, int)) and 'humidity' in data:
                    demo_received.set()
            except (ValueError, KeyError, TypeError):
                pass

    client.on_connect, client.on_subscribe, client.on_message = on_connect, on_subscribe, on_message
    created = False
    try:
        with engine.begin() as connection:
            connection.execute(text('''INSERT INTO "Tag_Journal"
                ("Tag_ID", "Tag_Name", "Creation_Date") VALUES (:id, :tag, :date)'''),
                {'id': identity, 'tag': device, 'date': date})
            connection.execute(text('''INSERT INTO "Device_Configuration"
                ("Device_ID", "Algorithm_ID", "Tag_ID", "Configuration_Update_Date")
                VALUES (:id, 1, :id, :date)'''), {'id': identity, 'date': date})
        created = True
        client.connect(os.environ.get('MQTT_HOST', 'localhost'),
                       int(os.environ.get('MQTT_PORT', '1883')), 60)
        client.loop_start()
        if not subscribed.wait(10):
            raise TimeoutError('Smoke observer subscription timed out')

        def publish(payload):
            info = client.publish(topic, payload, qos=1)
            info.wait_for_publish(timeout=10)
            if not info.is_published():
                raise TimeoutError('Smoke publish acknowledgment timed out')

        def valid_packet():
            sensor = {'temperature': 99.0, 'humidity': 50.0,
                      'timestamp': datetime.now(timezone.utc).isoformat()}
            return encrypt_data(json.dumps(sensor), key)

        def anomaly_count():
            with engine.connect() as connection:
                return connection.execute(text('''SELECT count(*) FROM "Anomalies"
                    WHERE "Device_ID" = :id'''), {'id': identity}).scalar_one()

        publish(json.dumps(valid_packet()))
        wait_for(lambda: anomaly_count() == 1, 'First encrypted packet was not persisted')
        publish(b'invalid-json')
        broken = valid_packet()
        ciphertext = base64.b64decode(broken['ciphertext'])
        broken['ciphertext'] = base64.b64encode(
            ciphertext[:-1] + bytes([ciphertext[-1] ^ 1])
        ).decode()
        publish(json.dumps(broken))
        publish(json.dumps(valid_packet()))
        wait_for(lambda: anomaly_count() >= 2, 'Receiver did not recover after malformed packets')
        if anomaly_count() != 2:
            raise AssertionError('Unexpected anomaly count (tampered/replayed/duplicate packet)')
        print('PASS: publisher AEAD -> Mosquitto -> receiver -> PostgreSQL (2 anomalies)')
        print('PASS: invalid JSON and modified tag rejected; receiver continued')
        if args.expect_demo:
            timeout = max(15, float(os.environ.get('PUBLISH_INTERVAL', '10')) + 5)
            if not demo_received.wait(timeout):
                raise TimeoutError('No encrypted packet observed from the demo publisher process')
            print('PASS: live demo publisher packet observed and decrypted')
    finally:
        client.disconnect()
        client.loop_stop()
        if created:
            with engine.begin() as connection:
                for table in ['Anomalies', 'Device_Configuration']:
                    connection.execute(text(f'DELETE FROM "{table}" WHERE "Device_ID" = :id'),
                                       {'id': identity})
                connection.execute(text('DELETE FROM "Tag_Journal" WHERE "Tag_ID" = :id'),
                                   {'id': identity})
        engine.dispose()


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Driver traceback locals may include passwords. Keep CLI output safe.
        print(f'Smoke check failed ({type(error).__name__})')
        raise SystemExit(1) from None

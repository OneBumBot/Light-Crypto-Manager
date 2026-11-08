"""Real TLS/ACL telemetry v2, tamper/replay checks with persistent sender state."""
import argparse
import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import threading
import time
import uuid

import paho.mqtt.client as mqtt
from sqlalchemy import create_engine, text
from src.runtime import database_url
from src.mqtt_transport import configure_client
from src.telemetry import encode_packet, decode_packet, load_registry, canonical, strict_json
from src.sequence import next_sequence


def wait_for(predicate, message, timeout=15):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if predicate(): return
        time.sleep(0.1)
    raise TimeoutError(message)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expect-demo',action='store_true')
    parser.add_argument('--replay-only',action='store_true')
    args=parser.parse_args()
    registry=load_registry()
    entry=registry['smoke']
    state=os.environ.get('PUBLISHER_STATE_FILE','/state/sequence.db')
    capture=Path(state).parent/'last-packet.json'
    engine=create_engine(database_url())
    client=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,client_id='smoke-'+uuid.uuid4().hex)
    configure_client(client)
    subscribed=threading.Event()
    demo=threading.Event()
    demo_sequence=[]
    def connected(c,u,f,rc,p):
        if rc==0: c.subscribe('iot/sensors/raspb1' if args.expect_demo else entry['topic'],qos=1)
    client.on_connect=connected
    client.on_subscribe=lambda *a: subscribed.set()
    # smoke has only its device key; validate actual publisher presence by the
    # authenticated broker subscription. Consumers verify raspb1's device key.
    def observed(c,u,m):
        try:
            value=strict_json(m.payload)
            if m.topic=='iot/sensors/raspb1' and value.get('schema_version')==2:
                ad=strict_json(base64.b64decode(value['associated_data']))
                demo_sequence.append(ad['sequence_number'])
                demo.set()
        except ValueError: pass
    client.on_message=observed
    def count():
        with engine.connect() as connection:
            return connection.execute(text('SELECT count(*) FROM "Anomalies" WHERE "Device_ID"=:id'),
                                      {'id':entry['database_device_id']}).scalar_one()
    def publish(value):
        info=client.publish(entry['topic'],value if isinstance(value,bytes) else json.dumps(value),qos=1)
        info.wait_for_publish(timeout=5)
        if not info.is_published(): raise TimeoutError('PUBACK timed out')
    def packet():
        return encode_packet({'temperature':99.0,'humidity':50.0,'timestamp':datetime.now(timezone.utc).isoformat()},
                             registry,'smoke',next_sequence(state,'smoke',entry['key_epoch']))
    try:
        client.connect(os.environ.get('MQTT_HOST','broker'),int(os.environ.get('MQTT_PORT','8883')),60)
        client.loop_start()
        if not subscribed.wait(10): raise TimeoutError('SUBACK timed out')
        baseline=count()
        if args.replay_only:
            publish(strict_json(capture.read_bytes()))
            time.sleep(1)
            if count()!=baseline: raise AssertionError('Replay accepted after restart')
            print('PASS: stored replay rejected after receiver restart')
            return
        first=packet()
        publish(first)
        wait_for(lambda:count()==baseline+1,'First packet not accepted')
        publish(first)
        publish(b'invalid-json')
        changed=dict(first)
        ct=base64.b64decode(changed['ciphertext'])
        changed['ciphertext']=base64.b64encode(ct[:-1]+bytes([ct[-1]^1])).decode()
        publish(changed)
        changed=dict(first)
        ad=strict_json(base64.b64decode(first['associated_data']))
        ad['sequence_number']+=100
        changed['associated_data']=base64.b64encode(canonical(ad)).decode()
        publish(changed)
        second=packet()
        publish(second)
        wait_for(lambda:count()>=baseline+2,'Receiver failed to recover')
        if count()!=baseline+2: raise AssertionError('Duplicate/tampered packet accepted')
        fd=os.open(capture,os.O_CREAT|os.O_TRUNC|os.O_WRONLY,0o600)
        with os.fdopen(fd,'w') as file: json.dump(second,file)
        print('PASS: TLS publisher -> broker -> receiver -> PostgreSQL')
        print('PASS: ciphertext/AAD corruption, replay and malformed JSON rejected; next packet accepted')
        if args.expect_demo:
            if not demo.wait(15): raise TimeoutError('No real publisher packet observed')
            def demo_accepted():
                with engine.connect() as connection:
                    value=connection.execute(text("SELECT last_sequence FROM mqtt_replay_state WHERE consumer='receiver' AND device_id='raspb1' AND key_epoch=1")).scalar()
                    return value is not None and value>=demo_sequence[0]
            wait_for(demo_accepted,'Real publisher packet was not authenticated by receiver')
            print('PASS: live publisher v2 packet authenticated and accepted by receiver')
    finally:
        client.disconnect();client.loop_stop();engine.dispose()


if __name__=='__main__':
    try: main()
    except Exception as error:
        print(f'Smoke check failed ({type(error).__name__})')
        raise SystemExit(1) from None

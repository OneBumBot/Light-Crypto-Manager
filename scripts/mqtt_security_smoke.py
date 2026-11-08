"""Exercise real TLS authentication and broker ACLs; never print credentials."""
import os
from pathlib import Path
import ssl
import threading
import time
import uuid

import paho.mqtt.client as mqtt
from src.mqtt_transport import configure_client


def connect(role, *, wrong_password=False, untrusted=False):
    client=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id='security-'+uuid.uuid4().hex,
                       protocol=mqtt.MQTTv5)
    root=Path('/run/lcm')
    configure_client(client,username=role,password_file=root/(role+'.password'),
                     ca_file=root/('untrusted.crt' if untrusted else 'ca.crt'))
    if wrong_password: client.username_pw_set(role,'intentionally-invalid-test-password')
    ready=threading.Event()
    result={}
    def connected(c,u,f,rc,p):
        result['denied']=rc.is_failure
        ready.set()
    client.on_connect=connected
    client.connect(os.environ.get('MQTT_HOST','broker'),int(os.environ.get('MQTT_PORT','8883')),60)
    client.loop_start()
    if not ready.wait(5):
        client.disconnect();client.loop_stop()
        raise TimeoutError('No CONNACK')
    return client,result['denied']


def main():
    clients=[]
    try:
        good,denied=connect('publisher');clients.append(good)
        assert not denied
        print('PASS: trusted TLS and publisher credentials')
        wrong,denied=connect('publisher',wrong_password=True);clients.append(wrong)
        assert denied
        print('PASS: incorrect password rejected')
        try:
            client,_=connect('publisher',untrusted=True)
            clients.append(client)
        except ssl.SSLCertVerificationError:
            print('PASS: untrusted CA rejected')
        else: raise AssertionError('Untrusted TLS certificate accepted')
        ack=threading.Event();codes=[]
        def published(c,u,mid,rc,p): codes.append(rc.is_failure);ack.set()
        good.on_publish=published
        good.publish('iot/sensors/smoke',b'forbidden-write',qos=1)
        assert ack.wait(5) and codes[-1]
        print('PASS: publisher cannot write another device topic')
        for role in ['web','receiver']:
            reader,denied=connect(role);clients.append(reader);assert not denied
            reader.on_publish=published;ack.clear()
            reader.publish('iot/sensors/raspb1',b'forbidden-write',qos=1)
            assert ack.wait(5) and codes[-1]
            print(f'PASS: {role} cannot publish telemetry')
        web=next(client for client in clients if client._username==b'web')
        positive=threading.Event();negative=threading.Event();subscribed=threading.Event()
        marker=uuid.uuid4().hex.encode()
        web.on_message=lambda c,u,m: positive.set() if m.payload==marker else None
        web.on_subscribe=lambda *a: subscribed.set()
        web.subscribe('iot/sensors/smoke',qos=1);assert subscribed.wait(5)
        subscribed.clear()
        good.on_message=lambda c,u,m: negative.set() if m.payload==marker else None
        good.on_subscribe=lambda *a: subscribed.set()
        good.subscribe('iot/sensors/smoke',qos=1);assert subscribed.wait(5)
        smoke,denied=connect('smoke');clients.append(smoke);assert not denied
        smoke.publish('iot/sensors/smoke',marker,qos=1).wait_for_publish(timeout=5)
        assert positive.wait(5)
        time.sleep(0.5)
        assert not negative.is_set()
        print('PASS: allowed reader receives probe; publisher cannot read forbidden topic')
    finally:
        for client in clients: client.disconnect();client.loop_stop()


if __name__=='__main__':
    try: main()
    except Exception as error:
        print(f'Transport security check failed ({type(error).__name__})')
        raise SystemExit(1) from None

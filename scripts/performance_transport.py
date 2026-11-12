"""Actual live-agent packet replay and MQTT TLS/ACL assertions; no generated AEAD."""
import base64,json,ssl,time,uuid
from threading import Event
from pathlib import Path
import paho.mqtt.client as mqtt
from sqlalchemy import create_engine,select,func
from src.runtime import database_url
from src.mqtt_transport import configure_client
from src.device_control.config import load
from src.outbox import outbox,metrics
from src.device_control import models as m


def main():
    config=load();engine=create_engine(database_url());clients=[];checks=[]
    def connect(role,wrong=False,untrusted=False):
        event=Event();status={};client=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,client_id='perf-probe-'+uuid.uuid4().hex,protocol=mqtt.MQTTv5)
        configure_client(client,username=role,password_file=Path('/run/lcm')/(role+'.password'),ca_file=Path('/run/lcm')/('untrusted.crt' if untrusted else 'ca.crt'))
        if wrong:client.username_pw_set(role,'invalid-controlled-lab-password')
        client.on_connect=lambda c,u,f,rc,p:(status.update(denied=rc.is_failure),event.set())
        client.connect('broker',8883,30);client.loop_start();clients.append(client);assert event.wait(5)
        return client,status['denied']
    def replay_count():
        with engine.connect() as c:return int(c.scalar(select(func.coalesce(func.sum(metrics.c.count),0)).where(metrics.c.kind=='replay')))
    try:
        observer,denied=connect('web');assert not denied
        connected=Event();packet=Event();wire={}
        observer.on_subscribe=lambda c,u,mid,reasons,p:connected.set() if reasons and all(not r.is_failure for r in reasons) else None
        def captured(c,u,msg):
            if not wire:wire.update(payload=bytes(msg.payload));packet.set()
        observer.on_message=captured;observer.subscribe(config['alpha']['registry']['topic'],qos=1)
        assert connected.wait(5) and packet.wait(5)
        outer=json.loads(wire['payload']);ad=json.loads(base64.b64decode(outer['associated_data']));assert ad['device_id']=='alpha'
        def identity_count():
            with engine.connect() as c:return c.scalar(select(func.count()).select_from(outbox).where(outbox.c.device_id=='alpha',outbox.c.key_epoch==ad['key_epoch'],outbox.c.sequence_number==ad['sequence_number']))
        end=time.monotonic()+10
        while identity_count()!=1 and time.monotonic()<end:time.sleep(.1)
        assert identity_count()==1
        with engine.connect() as c:before=c.execute(select(m.devices.c.effective_profile,m.devices.c.effective_event).where(m.devices.c.device_id=='alpha')).one()
        device,denied=connect('device_alpha');assert not denied;replay=replay_count()
        result=device.publish(config['alpha']['registry']['topic'],wire['payload'],qos=1);result.wait_for_publish(5);assert result.is_published()
        end=time.monotonic()+10
        while replay_count()<replay+1 and time.monotonic()<end:time.sleep(.1)
        assert replay_count()>=replay+1 and identity_count()==1
        with engine.connect() as c:assert c.execute(select(m.devices.c.effective_profile,m.devices.c.effective_event).where(m.devices.c.device_id=='alpha')).one()==before
        checks.append('actual_packet_replay_no_duplicate_admission_or_effective')
        for client,topic in [(device,config['beta']['registry']['topic']),(observer,config['alpha']['registry']['topic'])]:
            ack=Event();codes=[];client.on_publish=lambda c,u,mid,rc,p:(codes.append(rc.is_failure),ack.set())
            client.publish(topic,b'bounded-forbidden-probe',qos=1);assert ack.wait(5) and codes[-1]
        checks+=['device_cannot_publish_neighbor','web_cannot_publish_telemetry']
        _,denied=connect('device_alpha',wrong=True);assert denied;checks.append('incorrect_password_denied')
        try:connect('web',untrusted=True)
        except ssl.SSLCertVerificationError:checks.append('untrusted_ca_denied')
        else:raise AssertionError('Untrusted CA accepted')
        print(json.dumps(dict(real_tls=True,profile=outer['profile'],captured_device='alpha',captured_epoch=ad['key_epoch'],captured_sequence=ad['sequence_number'],unique_identity_count=identity_count(),checks=checks,exit_code=0)))
    finally:
        for client in clients:client.disconnect();client.loop_stop()
        engine.dispose()

if __name__=='__main__':main()

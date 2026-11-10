"""Optional live worker. Bounded inbox, durable delivery, manual control only."""
import os,queue,signal,time,logging
from pathlib import Path
from threading import Event
import paho.mqtt.client as mqtt
from sqlalchemy import create_engine,select,func,update
from sqlalchemy.dialects.postgresql import insert
from src.runtime import database_url
from src.mqtt_transport import configure_client
from .config import load
from .protocol import topic,open_message,seal
from . import server,models as m


def main():
    logging.basicConfig(level=logging.INFO);log=logging.getLogger(__name__)
    if os.environ.get('CONTROL_MODE')!=server.MODE or os.environ.get('MQTT_INSECURE_TEST_MODE')=='1':raise ValueError('Manual mode and TLS required')
    config=load();stop=Event();connected=Event();inbox=queue.Queue(maxsize=256);ready=Path('/tmp/control-ready');ready.unlink(missing_ok=True)
    engine=create_engine(database_url(),pool_pre_ping=True,connect_args={'connect_timeout':3,'options':'-cstatement_timeout=4000 -clock_timeout=2000'})
    client=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,client_id='live-controller-'+os.environ.get('HOSTNAME','local'))
    configure_client(client)
    def connect(c,u,f,rc,p):
        if rc==0:c.subscribe([(topic(d,'device'),1) for d in config])
    def subscribed(c,u,mid,reasons,p):
        if reasons and all(not r.is_failure for r in reasons):connected.set()
    def incoming(c,u,msg):
        if msg.retain or len(msg.payload)>8192:return
        try:inbox.put_nowait((bytes(msg.payload),msg.topic))
        except queue.Full:c.disconnect()
    client.on_connect=connect;client.on_subscribe=subscribed;client.on_message=incoming;client.on_disconnect=lambda *_:connected.clear()
    client.reconnect_delay_set(1,5)
    for s in [signal.SIGINT,signal.SIGTERM]:signal.signal(s,lambda *_:stop.set())
    try:
        client.connect(os.environ.get('MQTT_HOST','broker'),int(os.environ.get('MQTT_PORT','8883')),30);client.loop_start()
        while not stop.is_set():
            try:
                if not connected.is_set():ready.unlink(missing_ok=True);stop.wait(.2);continue
                try:raw,t=inbox.get(timeout=.1)
                except queue.Empty:raw=None
                if raw:
                    device=next((d for d in config if topic(d,'device')==t),None)
                    try:
                        if device is None:raise ValueError('Unknown control device')
                        body=open_message(raw,bytes.fromhex(config[device]['status_key']),'device',device,t)
                        response=None
                        with engine.begin() as c:
                            if body['kind']=='lease_request':response=server.grant(c,body)
                            elif body['kind']=='ack':server.handle_ack(c,body)
                            else:raise ValueError('Unexpected status kind')
                        if response:client.publish(topic(device,'controller'),seal(response,bytes.fromhex(config[device]['command_key']),'controller'),qos=1)
                    except ValueError:log.warning('Control input safely rejected')
                with engine.begin() as c:cmd=server.claim(c,config)
                if cmd:
                    outcome=client.publish(topic(cmd['device_id'],'controller'),cmd['wire'].encode(),qos=1,retain=False)
                    outcome.wait_for_publish(timeout=2)
                    if outcome.is_published():
                        with engine.begin() as c:server.delivery_finished(c,cmd)
                with engine.begin() as c:
                    if c.scalar(select(func.count()).select_from(m.devices).where(m.devices.c.device_id.in_(list(config))))!=len(config):raise ValueError('Provisioning unavailable')
                    n=server.now(c)
                    c.execute(insert(m.workers).values(id=os.environ.get('HOSTNAME','local'),heartbeat=n,status='ready').on_conflict_do_update(index_elements=['id'],set_={'heartbeat':n,'status':'ready'}))
                ready.touch()
            except Exception as e:
                ready.unlink(missing_ok=True);log.warning('Control temporarily unavailable (%s)',type(e).__name__);stop.wait(1)
    finally:
        ready.unlink(missing_ok=True);client.disconnect();client.loop_stop();engine.dispose()

if __name__=='__main__':main()

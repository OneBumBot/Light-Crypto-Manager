"""Existing real TLS/ACL/replay probe plus a captured-packet AEAD-tag negative."""
import base64
from contextlib import redirect_stdout
import hashlib
import io
import json
import time
from threading import Event
import paho.mqtt.client as mqtt
from sqlalchemy import create_engine,select,func
from src.runtime import database_url
from src.device_control.config import load
from src.mqtt_transport import configure_client
from src.outbox import metrics,outbox
from src.telemetry import canonical


def main():
    from scripts.performance_transport import main as transport
    output=io.StringIO()
    with redirect_stdout(output):transport()
    transport_report=json.loads(output.getvalue())
    config=load()['alpha'];engine=create_engine(database_url());clients=[]
    def metric(kind):
        with engine.connect() as c:return int(c.scalar(select(func.coalesce(func.sum(metrics.c.count),0)).where(metrics.c.kind==kind)))
    def connect(user,password):
        ready=Event();client=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,protocol=mqtt.MQTTv5)
        configure_client(client,username=user,password_file='/run/lcm/'+password,ca_file='/run/lcm/ca.crt')
        client.on_connect=lambda c,u,f,r,p:ready.set() if r==0 else None
        client.connect('broker',8883,30);client.loop_start();clients.append(client);assert ready.wait(5);return client
    try:
        observer=connect('web','web.password');captured=Event();subscribed=Event();packets=[]
        observer.on_subscribe=lambda *args:subscribed.set()
        observer.on_message=lambda c,u,m:(packets.append(bytes(m.payload)),captured.set())
        observer.subscribe(config['registry']['topic'],qos=1);assert subscribed.wait(5) and captured.wait(5)
        raw=packets[0];value=json.loads(raw);identity=json.loads(base64.b64decode(value['associated_data']))
        encoded=base64.b64decode(value['ciphertext']);value['ciphertext']=base64.b64encode(encoded[:-1]+bytes([encoded[-1]^1])).decode()
        rejected=metric('rejected');device=connect('device_alpha','device_alpha.password')
        sent=device.publish(config['registry']['topic'],canonical(value),qos=1);sent.wait_for_publish(5);assert sent.is_published()
        until=time.monotonic()+12
        while time.monotonic()<until and metric('rejected')==rejected:time.sleep(.1)
        assert metric('rejected')==rejected+1, 'Tag failure must be authentication rejection, not normal/replay admission'
        with engine.connect() as c:
            duplicates=c.scalar(select(func.count()).select_from(outbox).where(outbox.c.device_id=='alpha',outbox.c.key_epoch==identity['key_epoch'],outbox.c.sequence_number==identity['sequence_number']))
        assert duplicates==1
        print(json.dumps(dict(transport=transport_report,tag_failure=dict(captured_packet_sha256=hashlib.sha256(raw).hexdigest(),device_id='alpha',key_epoch=identity['key_epoch'],sequence_number=identity['sequence_number'],profile=value['profile'],rejected_increment=1,identity_admissions=duplicates,new_encryption_invocations=0),scope='Actual Stage16 localhost/internal lab only; captured ciphertext bit flip, no fabricated accepted record',exit_code=0),indent=2))
    finally:
        for client in clients:client.disconnect();client.loop_stop()
        engine.dispose()

if __name__=='__main__':main()

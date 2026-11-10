"""Real Python MQTT/TLS device: control agent + telemetry publisher, not simulator."""
import os,signal,time,queue,logging,uuid
from pathlib import Path
from threading import Event
from datetime import datetime,timezone
import paho.mqtt.client as mqtt
from src.mqtt_transport import configure_client
from src.telemetry import encode_packet,canonical
from .config import load
from .protocol import topic,message,seal,open_message
from .state import DeviceState

log=logging.getLogger(__name__)


def main():
    logging.basicConfig(level=logging.INFO)
    if os.environ.get('MQTT_INSECURE_TEST_MODE')=='1':raise ValueError('Live agent requires TLS')
    if (os.environ.get('CONTROL_DROP_ACTIVATE_ACK')=='1' or os.environ.get('CONTROL_TEST_READY_DELAY')) and os.environ.get('APP_ENV')!='test':raise ValueError('Fault injection restricted to explicit test mode')
    delay=float(os.environ.get('CONTROL_TEST_READY_DELAY','0'))
    if not 0<=delay<=5:raise ValueError('Bounded test delay')
    device=os.environ['DEVICE_ID'];config=load()[device]
    state=DeviceState(os.environ['DEVICE_STATE_FILE'],device,config['command_epoch'])
    inbox=queue.Queue(maxsize=128);stop=Event();connected=Event();boot=str(uuid.uuid4());grant=None;request=None
    seq=0;ready=Path('/tmp/device-ready');ready.unlink(missing_ok=True)
    interval=float(os.environ.get('PUBLISH_INTERVAL','.5'))
    if not .05<=interval<=60:raise ValueError('Bounded device interval required')
    client=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,client_id='live-device-'+device)
    configure_client(client)
    def connect(c,u,f,rc,p):
        if rc==0:c.subscribe(topic(device,'controller'),qos=1)
    def subscribed(c,u,mid,reasons,p):
        if reasons and all(not r.is_failure for r in reasons):connected.set()
    def incoming(c,u,m):
        if m.retain or len(m.payload)>8192:return
        try:inbox.put_nowait((bytes(m.payload),m.topic))
        except queue.Full:stop.set()
    client.on_connect=connect;client.on_subscribe=subscribed;client.on_message=incoming
    client.on_disconnect=lambda *_:connected.clear()
    client.reconnect_delay_set(1,5)
    for s in [signal.SIGINT,signal.SIGTERM]:signal.signal(s,lambda *_:stop.set())
    next_publish=0;next_lease=0
    try:
        client.connect(os.environ.get('MQTT_HOST','broker'),int(os.environ.get('MQTT_PORT','8883')),30);client.loop_start()
        while not stop.is_set():
            n=time.monotonic()
            if not connected.is_set():ready.unlink(missing_ok=True)
            elif grant:ready.touch()
            if connected.is_set() and (grant is None or seq>grant['data']['last_sequence']) and n>=next_lease:
                from .protocol import utc
                if request is not None and utc(request['expires_at'])<=datetime.now(timezone.utc):request=None
                if request is None:
                    boot=str(uuid.uuid4())
                    request=message(device,'lease_request',dict(boot_id=boot,key_epoch=config['command_epoch'],local_profile=state.read()['profile']))
                client.publish(topic(device,'device'),seal(request,bytes.fromhex(config['status_key']),'device'),qos=1)
                next_lease=n+2
            try:raw,t=inbox.get(timeout=.05)
            except queue.Empty:raw=None
            if raw is not None:
                try:
                    body=open_message(raw,bytes.fromhex(config['command_key']),'controller',device,t)
                    if body['kind']=='lease_grant':
                        d=body['data']
                        if request is None or d['request_id']!=request['message_id'] or d['boot_id']!=boot:raise ValueError('Unsolicited/stale lease')
                        if d['key_epoch']!=config['command_epoch']:raise ValueError('Lease key epoch')
                        local=state.read()
                        if local['seq']<d['command_floor']:raise ValueError('Restored stale command ledger requires recovery')
                        if d['effective_profile'] and local['profile'] not in [d['effective_profile'],d['pending_profile']]:raise ValueError('Restored profile requires recovery')
                        state.accept_lease(d['first_sequence'],d['last_sequence'])
                        grant=body;seq=d['first_sequence'];request=None;ready.touch()
                    elif body['kind']=='command':
                        if grant is None:raise ValueError('Boot reconciliation incomplete')
                        ack=state.execute(body,config)
                        if body['data']['phase']=='PREPARE' and delay:stop.wait(delay)
                        if os.environ.get('CONTROL_DROP_ACTIVATE_ACK')!='1' or body['data']['phase']!='ACTIVATE':
                            client.publish(topic(device,'device'),ack,qos=1)
                        log.info('Authenticated device command executed or exact retry answered')
                except ValueError:
                    log.warning('Control message safely rejected')
            if connected.is_set() and grant and seq<=grant['data']['last_sequence'] and n>=next_publish:
                sensor=dict(temperature=23.5,humidity=48.0,timestamp=datetime.now(timezone.utc).isoformat())
                current=seq;seq+=1 # discard on any failure; ranges are never restored on a new process
                packet=encode_packet(sensor,{device:config['registry']},device,current,profile=state.read()['profile'])
                result=client.publish(config['registry']['topic'],canonical(packet),qos=1)
                # Paho retransmits the same payload bytes. No retry calls encode_packet again.
                if result.rc!=mqtt.MQTT_ERR_SUCCESS:log.warning('Telemetry publish not queued; sequence discarded')
                next_publish=n+interval
    finally:
        ready.unlink(missing_ok=True);client.disconnect();client.loop_stop();state.close()

if __name__=='__main__':main()

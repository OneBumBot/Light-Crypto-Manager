"""Negative control inputs over actual TLS/MQTT, plus live HTTP RBAC/CSRF."""
import os,json,time,copy,uuid,hashlib,hmac,secrets,re
from datetime import datetime,timezone,timedelta
from threading import Event
import paho.mqtt.client as mqtt
import requests
from sqlalchemy import create_engine,select,func
from src.runtime import database_url
from src.mqtt_transport import configure_client
from src.telemetry import canonical
from src.device_control.config import load
from src.device_control.protocol import seal,topic,DOMAIN,CONTROLLER
from src.device_control import models as m
from src.web.app import app
from src.web.models import db,User


def main():
    config=load();engine=create_engine(database_url());checks=[]
    def connect(user,path):
        ready=Event();client=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,protocol=mqtt.MQTTv5)
        configure_client(client,username=user,password_file=path,ca_file='/run/lcm/ca.crt')
        client.on_connect=lambda c,u,f,r,p:ready.set() if r==0 else None
        client.connect('broker',8883,30);client.loop_start();assert ready.wait(5);return client
    controller=connect('controller','/run/control/controller.password')
    device=connect('device_alpha','/run/lcm/device_alpha.password')
    observed=[];sub_ready=Event()
    controller.on_subscribe=lambda c,u,mid,codes,p:sub_ready.set() if all(not code.is_failure for code in codes) else None
    controller.subscribe(topic('alpha','device'),qos=1);assert sub_ready.wait(5)
    controller.on_message=lambda c,u,msg:observed.append(bytes(msg.payload))
    try:
        with engine.connect() as c:
            cmd=c.execute(select(m.commands).where(m.commands.c.device_id=='alpha',m.commands.c.phase=='ACTIVATE').order_by(m.commands.c.sequence.desc()).limit(1)).mappings().one()
            initial=dict(c.execute(select(m.devices).where(m.devices.c.device_id=='alpha')).mappings().one())
            ack=c.execute(select(m.acks).where(m.acks.c.command_id==cmd['id'])).mappings().first()
            ack_count=c.scalar(select(func.count()).select_from(m.acks))
        def forced_wire(body,key,direction):
            # Explicit adversarial fixture encoder bypasses producer validation; receiver must reject it.
            signed=dict(domain=DOMAIN,direction=direction,topic=topic(body['device_id'],direction),body=body)
            return canonical(dict(**signed,mac=hmac.new(key,canonical(signed),hashlib.sha256).hexdigest()))
        base=copy.deepcopy(cmd['body']);now=datetime.now(timezone.utc)
        base['created_at']=now.isoformat();base['expires_at']=(now+timedelta(seconds=60)).isoformat()
        bad=[]
        raw=forced_wire(base,bytes.fromhex(config['alpha']['command_key']),'controller')
        invalid=json.loads(raw);invalid['mac']=('0' if invalid['mac'][0]!='0' else '1')+invalid['mac'][1:]
        bad.append(('invalid_mac',canonical(invalid),topic('alpha','controller')))
        malformed=json.loads(raw);malformed['mac']='é'*64
        bad.append(('invalid_unicode_mac',canonical(malformed),topic('alpha','controller')))
        bad.append(('wrong_key_direction',forced_wire(base,bytes.fromhex(config['alpha']['status_key']),'controller'),topic('alpha','controller')))
        bad.append(('wrong_device_topic',raw,topic('beta','controller')))
        for field,val in [('requested_profile','unavailable-profile'),('command_epoch',0),('command_sequence',base['data']['command_sequence']),('controller_identity','unauthorized-controller')]:
            b=copy.deepcopy(base);b['data'][field]=val
            if field=='command_sequence':b['message_id']=str(uuid.uuid4());b['data']['command_id']=b['message_id']
            bad.append((field,forced_wire(b,bytes.fromhex(config['alpha']['command_key']),'controller'),topic('alpha','controller')))
        expired=copy.deepcopy(base);expired['created_at']=(now-timedelta(seconds=20)).isoformat();expired['expires_at']=(now-timedelta(seconds=10)).isoformat()
        bad.append(('expired_and_retained',forced_wire(expired,bytes.fromhex(config['alpha']['command_key']),'controller'),topic('alpha','controller')))
        for name,raw,t in bad:
            result=controller.publish(t,raw,qos=1,retain=name=='expired_and_retained');result.wait_for_publish(3);assert result.is_published();checks.append(name)
        # Device cannot publish any command, including to itself; controller cannot impersonate telemetry.
        def denied(client,t):
            done=Event();reasons=[]
            client.on_publish=lambda c,u,mid,rc,p:(reasons.append(rc),done.set())
            client.publish(t,b'not-authorized',qos=1);assert done.wait(4) and reasons[0].is_failure
        denied(device,topic('alpha','controller'));denied(device,topic('beta','device'));denied(controller,'iot/sensors/alpha')
        checks.extend(['device_cannot_command_itself','device_cannot_status_other_device','controller_cannot_publish_telemetry'])
        # Unauthorized command read must return a failing SUBACK.
        done=Event();codes=[]
        device.on_subscribe=lambda c,u,mid,rc,p:(codes.extend(rc),done.set())
        read_payloads=[];device.on_message=lambda c,u,msg:read_payloads.append(bytes(msg.payload))
        device.subscribe(topic('beta','controller'),qos=1);assert done.wait(4)
        marker=('inert-acl-probe-'+uuid.uuid4().hex).encode()
        controller.publish(topic('beta','controller'),marker,qos=1).wait_for_publish(3);time.sleep(.5)
        assert marker not in read_payloads
        checks.append('device_cannot_read_other_commands')
        time.sleep(1)
        assert not observed, 'Invalid commands produced a device response'
        injected_status=set()
        assert ack is not None, 'A recent normal authenticated ACTIVATE ACK is required for this probe'
        # Authenticated but contradictory ACKs cannot advance durable state.
        if ack:
            for field,val in [('correlation_id',str(uuid.uuid4())),('requested_profile','ascon-aead128-v1' if cmd['body']['data']['requested_profile']!='ascon-aead128-v1' else 'aes-128-gcm-v1')]:
                b=copy.deepcopy(ack['body']);b['message_id']=str(uuid.uuid4());b['created_at']=now.isoformat();b['expires_at']=(now+timedelta(seconds=60)).isoformat();b['data'][field]=val
                forged=forced_wire(b,bytes.fromhex(config['alpha']['status_key']),'device');injected_status.add(hashlib.sha256(forged).hexdigest())
                result=device.publish(topic('alpha','device'),forged,qos=1);result.wait_for_publish(3)
                checks.append('ack_wrong_'+field)
            # Exact duplicate is harmless if still within TTL, otherwise safely expires.
            duplicate=forced_wire(ack['body'],bytes.fromhex(config['alpha']['status_key']),'device');injected_status.add(hashlib.sha256(duplicate).hexdigest())
            r=device.publish(topic('alpha','device'),duplicate,qos=1);r.wait_for_publish(3);checks.append('duplicate_ack_no_new_record')
        time.sleep(2)
        with engine.connect() as c:
            current=c.execute(select(m.devices).where(m.devices.c.device_id=='alpha')).mappings().one()
            assert current['effective_profile']==initial['effective_profile'] and current['command_acknowledged']==initial['command_acknowledged']
            assert c.scalar(select(func.count()).select_from(m.acks))==ack_count
        from src.outbox import outbox
        with engine.connect() as c:first=c.scalar(select(func.max(outbox.c.sequence_number)).where(outbox.c.device_id=='alpha'))
        time.sleep(1.2)
        with engine.connect() as c:assert c.scalar(select(func.max(outbox.c.sequence_number)).where(outbox.c.device_id=='alpha'))>first
        checks.append('device_continues_telemetry_after_invalid_control')
        assert all(hashlib.sha256(raw).hexdigest() in injected_status for raw in observed) # exclude our own adversarial status publications
        # Clear retained invalid command, never retained valid commands.
        controller.publish(topic('alpha','controller'),b'',qos=1,retain=True).wait_for_publish(3)
        username='ctrl-viewer-'+uuid.uuid4().hex[:10];password=secrets.token_urlsafe(24);uid=None
        try:
            with app.app_context():
                u=User(username=username,email=username+'@example.test',role='viewer');u.set_password(password);db.session.add(u);db.session.commit();uid=u.id
            http=requests.Session();url='http://web:5000'
            assert requests.get(url+'/api/control',timeout=5).status_code==401
            token=re.search(r'name="csrf-token" content="([^"]+)"',http.get(url+'/login',timeout=5).text).group(1)
            assert http.post(url+'/login',data=dict(username=username,password=password,csrf_token=token),allow_redirects=False,timeout=5).status_code==302
            r=http.get(url+'/control',timeout=5);token=re.search(r'name="csrf-token" content="([^"]+)"',r.text).group(1)
            r=http.post(url+'/api/control/alpha/switch',json={'profile':'aes-128-gcm-v1','ttl':120},headers={'X-CSRFToken':token},timeout=5);assert r.status_code==403
            assert http.get(url+'/api/control',timeout=5).status_code==200
            checks.extend(['anonymous_http_denied','viewer_http_control_denied','viewer_status_allowed'])
        finally:
            if uid:
                with app.app_context():u=db.session.get(User,uid);db.session.delete(u);db.session.commit()
        print(json.dumps(dict(real_tls=True,checks=checks,invalid_commands_created_ack=0,effective_unchanged=True,live_control_hmac=True),indent=2))
    finally:
        controller.disconnect();controller.loop_stop();device.disconnect();device.loop_stop();engine.dispose()

if __name__=='__main__':main()

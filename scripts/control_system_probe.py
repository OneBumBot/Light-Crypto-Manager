"""Real stage8 PG/Mongo/MQTT/HTTP probe; never trains ML or simulates device ACK."""
import os,time,json,re,secrets,uuid,argparse
from datetime import datetime,timezone
from pathlib import Path
import requests
from sqlalchemy import create_engine,select,func,text
from src.runtime import database_url
from src.device_control import server,models as m
from src.device_control.config import load
from src.crypto_profiles import ASCON,AES
from src.outbox import outbox


def wait(predicate,seconds=30):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        result=predicate()
        if result:return result
        time.sleep(.2)
    raise AssertionError('Expected real control state/telemetry not observed before deadline')


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['setup','roundtrip','status','switch-aes','request-aes','request-ascon','request-aes-short','reconcile']);a=p.parse_args()
    engine=create_engine(database_url(),pool_pre_ping=True)
    if a.action=='setup':
        from scripts.seed_demo import seed_demo
        from scripts.provision_registry import main as provision_registry
        from src.web.app import app
        with app.app_context():seed_demo()
        provision_registry()
        with engine.begin() as c:server.provision(c,load())
        print(json.dumps({'setup':'committed','devices':list(load()),'keys_printed':False}));return
    if a.action=='status':
        with engine.connect() as c:
            telemetry={r.device_id:dict(accepted=r.count,max_sequence=r.maximum) for r in c.execute(select(outbox.c.device_id,func.count().label('count'),func.max(outbox.c.sequence_number).label('maximum')).group_by(outbox.c.device_id))}
            rows=c.execute(select(m.devices)).mappings().all();trans=c.execute(select(m.transitions).order_by(m.transitions.c.created_at)).mappings().all()
        def safe(row):return {k:v.isoformat() if isinstance(v,datetime) else v for k,v in row.items() if k!='key_fingerprint'}
        print(json.dumps(dict(telemetry=telemetry,devices=[safe(r) for r in rows],transitions=[safe(r) for r in trans]),indent=2));return
    from src.web.app import app
    from src.web.models import User,db
    username='ctrl-probe-'+uuid.uuid4().hex[:10];password=secrets.token_urlsafe(24)
    with app.app_context():
        user=User(username=username,email=username+'@example.test',role='admin');user.set_password(password);db.session.add(user);db.session.commit();user_id=user.id
    http=requests.Session();base='http://web:5000';measurements=[]
    try:
        def token(path):
            r=http.get(base+path,timeout=5);r.raise_for_status();match=re.search(r'name="csrf-token" content="([^"]+)"',r.text)
            assert match;return match.group(1)
        r=http.post(base+'/login',data=dict(username=username,password=password,csrf_token=token('/login')),allow_redirects=False,timeout=5);assert r.status_code==302
        csrf=token('/control')
        def configured():
            with engine.connect() as c:return {r['device_id']:dict(r) for r in c.execute(select(m.devices)).mappings()}
        wait(lambda:all(configured().get(d,{}).get('effective_event') for d in ['alpha','beta','gamma']))
        from src.policy.models import worker_status as policy_workers, states as policy_states
        with engine.connect() as c:
            policy_modes=set(c.scalars(select(policy_workers.c.mode)))
            assert policy_modes=={'DRY_RUN'}, 'Run the actual DRY_RUN policy worker for this probe'
            assert c.scalar(select(func.count()).select_from(policy_states).where(policy_states.c.applied.is_not(None)))==0
        initial=configured();assert initial['beta']['effective_profile']==ASCON and initial['gamma']['effective_profile']==ASCON
        def switch(target):
            before=configured()['alpha']
            if before.get('last_request_at'):
                time.sleep(max(0,2.1-(datetime.now(timezone.utc)-before['last_request_at']).total_seconds()))
            start=time.perf_counter()
            if a.action=='reconcile':
                tid=before['pending_transition'];assert tid
                r=http.post(base+'/api/control/alpha/reconcile',json={'transition_id':tid,'ttl':60},headers={'X-CSRFToken':csrf},timeout=5)
            else:r=http.post(base+'/api/control/alpha/switch',json={'profile':target,'ttl':15 if a.action=='request-aes-short' else 120},headers={'X-CSRFToken':csrf},timeout=5)
            assert r.status_code==202,(r.status_code,r.text)
            tid=tid if a.action=='reconcile' else r.json()['transition_id']
            if a.action.startswith('request-'):
                measurements.append(dict(transition_id=tid,target=target,phase='PREPARED_SERVER',request_committed=True))
                return
            def confirmed():
                with engine.connect() as c:
                    t=c.execute(select(m.transitions).where(m.transitions.c.id==tid)).mappings().one()
                    return dict(t) if t['phase']=='EFFECTIVE_CONFIRMED' else None
            transition=wait(confirmed);elapsed=time.perf_counter()-start
            d=configured()['alpha'];assert d['effective_profile']==target and d['effective_event']!=before['effective_event']
            with engine.connect() as c:
                event=c.execute(select(outbox).where(outbox.c.id==d['effective_event'])).mappings().one()
                commands=c.execute(select(m.commands).where(m.commands.c.transition_id==tid).order_by(m.commands.c.sequence)).mappings().all()
                ack_count=c.scalar(select(func.count()).select_from(m.acks).where(m.acks.c.command_id.in_([cmd['id'] for cmd in commands])))
                from src.device_control.models import evidence
                receipt=c.execute(select(evidence).where(evidence.c.event_id==d['effective_event'])).mappings().one()
                assert receipt['profile']==target and receipt['sequence_number']==event['sequence_number'] and len(receipt['packet_sha256'])==64
                assert len(commands)==2 and commands[1]['sequence']>commands[0]['sequence']
                assert event['payload']['crypto_profile']==('AES-128-GCM' if target==AES else 'Ascon-AEAD128')
                assert event['sequence_number']>0
            from src.mongo_repository import MongoRepository
            repo=MongoRepository(role='relay')
            try:
                wait(lambda:repo.collection.find_one({'_id':f"alpha:{event['key_epoch']}:{event['sequence_number']}"}))
                stored=repo.collection.find_one({'_id':f"alpha:{event['key_epoch']}:{event['sequence_number']}"})
                assert stored['crypto_profile']==event['payload']['crypto_profile']
            finally:repo.close()
            assert configured()['beta']['effective_profile']==ASCON and configured()['gamma']['effective_profile']==ASCON
            measurements.append(dict(transition_id=tid,target=target,phase=transition['phase'],telemetry_event=event['id'],sequence_number=event['sequence_number'],
                full_http_to_effective_seconds=elapsed,command_sequences=[cmd['sequence'] for cmd in commands],authenticated_ack_count=ack_count,
                prepare_to_activate_seconds=(transition['activated_at']-transition['created_at']).total_seconds(),
                activate_to_effective_seconds=(transition['confirmed_at']-transition['activated_at']).total_seconds(),
                activate_to_ack_seconds=(transition['acknowledged_at']-transition['activated_at']).total_seconds() if transition['acknowledged_at'] else None))
        # HTTP RBAC/CSRF and rejected unsupported capabilities, without creating any transition.
        assert http.post(base+'/api/control/alpha/switch',json={'profile':AES,'ttl':120},timeout=5).status_code==400
        assert http.post(base+'/api/control/gamma/switch',json={'profile':AES,'ttl':120},headers={'X-CSRFToken':csrf},timeout=5).status_code==409
        switch(ASCON if a.action=='request-ascon' else AES)
        if a.action=='roundtrip':time.sleep(2.1);switch(ASCON)
        print(json.dumps(dict(environment='real isolated software IoT agents, Docker MQTT TLS/PG/Mongo/HTTP',policy_mode='DRY_RUN',measurements=measurements),indent=2))
    finally:
        with app.app_context():
            user=db.session.get(User,user_id)
            if user:db.session.delete(user);db.session.commit()
        http.close();engine.dispose()

if __name__=='__main__':main()

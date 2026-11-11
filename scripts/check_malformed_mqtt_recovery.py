"""Bounded poison probe. Host entry requires a dedicated lcm-stage8-fix-* project.
Runs a probe in the tests container; does not provision or delete volumes.
--baseline observes the original parser without claiming a successful recovery.
"""
import argparse
import base64
import copy
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


def inside(profile, baseline=False):
    from threading import Event
    import paho.mqtt.client as mqtt
    from sqlalchemy import create_engine, select, func
    from src.runtime import database_url
    from src.device_control.config import load
    from src.device_control import models as m
    from src.telemetry import encode_packet, canonical
    from src.mqtt_transport import configure_client
    from src.outbox import outbox, metrics
    from src.replay import replay_state
    from src.security_events import journal
    from src.mongo_repository import MongoRepository
    engine=create_engine(database_url());config=load();repo=MongoRepository(role='relay')
    clients=[]
    def wait(predicate, seconds=20):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            if predicate():return
            time.sleep(.1)
        raise AssertionError('Missing application-level evidence')
    def count(table):
        with engine.connect() as c:return c.scalar(select(func.count()).select_from(table))
    def metric(kind):
        with engine.connect() as c:return int(c.scalar(select(func.coalesce(func.sum(metrics.c.count),0)).where(metrics.c.kind==kind)))
    def connect(device):
        ready=Event();client=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,protocol=mqtt.MQTTv5)
        configure_client(client,username='device_'+device,password_file='/run/lcm/device_'+device+'.password',ca_file='/run/lcm/ca.crt')
        client.on_connect=lambda c,u,f,r,p:ready.set() if r==0 else None
        client.connect('broker',8883,30);client.loop_start();clients.append(client);assert ready.wait(5)
        return client
    def publish(client,device,packet):
        r=client.publish(config[device]['registry']['topic'],canonical(packet),qos=1)
        r.wait_for_publish(4);assert r.is_published() # transport only; assertions below require SQL/Mongo
    def next_seq(device):
        with engine.connect() as c:
            seq=(c.scalar(select(func.max(outbox.c.sequence_number)).where(outbox.c.device_id==device)) or 0)+1
            reserved=c.scalar(select(m.devices.c.sequence_reserved).where(m.devices.c.device_id==device))
            assert seq+3<=reserved
            return seq
    def packet(device,seq,p):
        return encode_packet(dict(temperature=23,humidity=48,timestamp=datetime.now(timezone.utc).isoformat()),
            {device:config[device]['registry']},device,seq,profile=p)
    def delivered(device,seq):return repo.collection.count_documents({'_id':f'{device}:1:{seq}'})==1
    def managed_mongo():return repo.collection.count_documents({'device_id':{'$in':list(config)}})
    def snapshot():
        with engine.connect() as c:
            return dict(replay=[dict(r) for r in c.execute(select(replay_state).order_by(replay_state.c.consumer,replay_state.c.device_id)).mappings()],
                effective=[dict(r) for r in c.execute(select(m.devices.c.device_id,m.devices.c.effective_profile,m.devices.c.effective_event).order_by(m.devices.c.device_id)).mappings()],
                evidence=count(m.evidence),outbox=count(outbox),mongo=managed_mongo(),
                mongo_total=repo.collection.count_documents({}),accepted=metric('accepted'))
    try:
        from src.crypto_profiles import ASCON
        alpha=connect('alpha');beta=connect('beta');seq=next_seq('alpha');bseq=next_seq('beta')
        n=count(outbox);accepted=metric('accepted')
        publish(alpha,'alpha',packet('alpha',seq,profile));wait(lambda:delivered('alpha',seq))
        assert count(outbox)==n+1 and metric('accepted')==accepted+1
        # Regression Mongo fixtures deliberately retain their separate test_* identities.
        wait(lambda:managed_mongo()==count(outbox))
        before=snapshot();rejects=metric('rejected');incoming=metric('incoming');observations=count(journal)
        good=packet('alpha',seq+1,profile);bad=[]
        for v in [[],{},None,True,1,1.5,['AES-128-GCM'],{'algorithm':'AES-128-GCM'},'unknown-profile']:
            p=copy.deepcopy(good);p['profile']=v;bad.append(p)
        for field in ['device_id','topic','key_epoch','sequence_number','profile']:
            p=copy.deepcopy(good);ad=json.loads(base64.b64decode(p['associated_data']));ad[field]=[]
            p['associated_data']=base64.b64encode(canonical(ad)).decode();bad.append(p)
        for field in ['nonce','ciphertext','associated_data']:
            p=copy.deepcopy(good);p[field]={};bad.append(p)
        if baseline:bad=bad[:2]
        started=time.monotonic()
        for p in bad:publish(alpha,'alpha',p)
        if not baseline:wait(lambda:metric('rejected')-rejects==len(bad))
        samples=[]
        # Bounded observation catches repeated delivery/incoming, not just publisher PUBACK.
        for _ in range(10):
            time.sleep(1)
            samples.append(dict(incoming=metric('incoming')-incoming,rejected=metric('rejected')-rejects))
        if baseline:
            print(json.dumps(dict(mode='baseline',sent=len(bad),samples=samples,seconds=time.monotonic()-started,
                admission_unchanged=snapshot()==before),indent=2));return
        assert snapshot()==before
        assert all(s==dict(incoming=len(bad),rejected=len(bad)) for s in samples)
        with engine.connect() as c:
            rejects_rows=c.execute(select(journal).where(journal.c.category=='rejected')).mappings().all()
            assert all(r['device_id'] is None and r['key_epoch'] is None and r['sequence_number'] is None for r in rejects_rows)
        assert count(journal)==observations+len(bad)
        publish(alpha,'alpha',good);wait(lambda:delivered('alpha',seq+1))
        replay=metric('replay');publish(alpha,'alpha',good);wait(lambda:metric('replay')==replay+1)
        publish(beta,'beta',packet('beta',bseq,ASCON));wait(lambda:delivered('beta',bseq))
        assert count(outbox)==before['outbox']+2 and metric('accepted')==before['accepted']+2
        assert managed_mongo()==before['mongo']+2
        assert repo.collection.count_documents({})==before['mongo_total']+2
        print(json.dumps(dict(profile=profile,malformed_sent=len(bad),rejected=len(bad),accepted=3,
            duplicate_admission=0,duplicate_replay=1,malformed_admission_state_unchanged=True,
            rejected_identity_null=True,neighbor_delivered=True,samples=samples,
            observation_seconds=time.monotonic()-started,postgres_mongo_count_delta=3),indent=2))
    finally:
        for c in clients:c.disconnect();c.loop_stop()
        repo.close();engine.dispose()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--env-file',type=Path);p.add_argument('--output',type=Path)
    p.add_argument('--inside',action='store_true');p.add_argument('--baseline',action='store_true')
    p.add_argument('--counters',action='store_true')
    p.add_argument('--profile',default='ascon-aead128-v1',choices=['ascon-aead128-v1','aes-128-gcm-v1'])
    a=p.parse_args()
    if a.counters:
        from sqlalchemy import create_engine,select,func
        from src.runtime import database_url
        from src.outbox import metrics
        engine=create_engine(database_url())
        try:
            with engine.connect() as c:
                rows=c.execute(select(metrics.c.kind,func.sum(metrics.c.count)).group_by(metrics.c.kind)).all()
                print(json.dumps({kind:int(total) for kind,total in rows}))
        finally:engine.dispose()
        return
    if a.inside:inside(a.profile,a.baseline);return
    if not a.env_file or not a.output:p.error('--env-file and --output required')
    env=dict(line.split('=',1) for line in a.env_file.read_text().splitlines() if '=' in line and not line.startswith('#'))
    import re
    project=env.get('COMPOSE_PROJECT_NAME','')
    if not re.fullmatch(r'lcm-stage8-fix-[a-z0-9-]+',project):p.error('Dedicated fix project required')
    if a.output.exists():p.error('Output already exists')
    base=['docker','compose','--env-file',str(a.env_file),'-f','compose.yaml','-f','compose.control.yaml','--profile','control']
    def run(*parts):
        r=subprocess.run(base+list(parts),capture_output=True,text=True,timeout=120)
        if r.returncode:
            a.output.with_suffix('.failure.txt').write_text(r.stdout+r.stderr)
            raise RuntimeError(f'Compose {parts[0]} exited {r.returncode}; see {a.output.with_suffix(".failure.txt")}')
        return r
    run('stop','device-alpha','device-beta','device-gamma')
    start=datetime.now(timezone.utc).isoformat();report={}
    try:
        script=str(Path(__file__).resolve())
        args=['run','--rm','--no-deps','-v',script+':/app/scripts/check_malformed_mqtt_recovery.py:ro','--entrypoint','python','tests','-m','scripts.check_malformed_mqtt_recovery','--inside','--profile',a.profile]
        if a.baseline:args.append('--baseline')
        r=run(*args);report=json.loads(r.stdout[r.stdout.index('{'):]);report.update(project=project,exit_code=r.returncode)
        logs=run('logs','--since',start,'receiver','broker').stdout
        a.output.with_suffix('.logs.txt').write_text(logs)
        report['receiver_processing_failures']=logs.count('MQTT packet processing failed')
        report['receiver_subscription_acknowledgements']=logs.count('MQTT subscription acknowledged')
        report['receiver_client_connections']=len(re.findall(r'New client connected .* as lightcrypto-ingestion ',logs))
        if not a.baseline:
            assert report['receiver_processing_failures']==0
            assert report['receiver_subscription_acknowledgements']==0
            assert report['receiver_client_connections']==0
            inspect=run('ps','--format','json','receiver').stdout
            assert 'healthy' in inspect
            def counters():
                r=run('run','--rm','--no-deps','-v',script+':/app/scripts/check_malformed_mqtt_recovery.py:ro',
                      '--entrypoint','python','tests','-m','scripts.check_malformed_mqtt_recovery','--counters')
                return json.loads(r.stdout[r.stdout.index('{'):])
            before_restart=counters()
            # Same persistent client/session: unacknowledged poison would redeliver here.
            run('up','-d','--no-deps','--force-recreate','--wait','receiver')
            time.sleep(5)
            after_restart=counters()
            assert after_restart==before_restart
            report.update(explicit_receiver_restart=True,post_restart_observation_seconds=5,
                          counters_before_restart=before_restart,counters_after_restart=after_restart,
                          no_redelivery_after_receiver_restart=True)
            restarted_logs=run('logs','--since',start,'receiver').stdout
            a.output.with_suffix('.restart.logs.txt').write_text(restarted_logs)
        a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
    finally:
        run('up','-d','--no-deps','--wait','device-alpha','device-beta','device-gamma')

if __name__=='__main__':main()

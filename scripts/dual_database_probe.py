"""Real TLS multi-device pipeline/recovery assertions in isolated Compose project."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
from threading import Event
import paho.mqtt.client as mqtt
from sqlalchemy import create_engine, select, func
from src.runtime import database_url
from src.telemetry import load_registry, encode_packet
from src.mqtt_transport import configure_client
from src.sequence import next_sequence
from src.outbox import outbox
from src.mongo_repository import MongoRepository

STATE=Path('/state/multidevice-packets.json')


def wait(predicate, timeout=30):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if predicate(): return
        time.sleep(0.2)
    raise AssertionError('Pipeline check timed out')


def publish(name,entry,packet):
    ready=Event()
    client=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect=lambda c,u,f,r,p:ready.set() if r==0 else None
    configure_client(client,username='device_'+name,password_file='/run/lcm/device_'+name+'.password')
    client.connect('broker',8883,30); client.loop_start()
    try:
        assert ready.wait(5)
        info=client.publish(entry['topic'],json.dumps(packet),qos=1)
        info.wait_for_publish(5)
        assert info.is_published()
    finally:
        client.disconnect(); client.loop_stop()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=['demo','publish','pending','delivered','replay','verify','identity'])
    args=parser.parse_args()
    registry=load_registry('/run/lcm/registry.json')
    engine=create_engine(database_url(),pool_pre_ping=True)
    repo=MongoRepository()
    try:
        if args.phase=='demo':
            wait(lambda: bool(repo.history(device='raspb1',limit=1)))
            print('PASS: publisher -> TLS broker -> ingestion -> PG outbox -> MongoDB')
            return
        devices={name:entry for name,entry in registry.items() if Path('/run/lcm/device_'+name+'.password').exists()}
        assert len(devices)>=3
        if args.phase=='publish':
            state={}
            for i,(name,entry) in enumerate(devices.items()):
                sequence=next_sequence('/state/multidevice-sequences.db',name,entry['key_epoch'])
                packet=encode_packet(dict(temperature=20+i,humidity=45+i,timestamp=datetime.now(timezone.utc).isoformat()),registry,name,sequence)
                state[name]=packet
                publish(name,entry,packet)
            STATE.write_text(json.dumps(state)); STATE.chmod(0o600)
            print('PASS: three independent TLS identities/keys/topics published')
            return
        state=json.loads(STATE.read_text())
        identities=[]
        import base64
        for name,packet in state.items():
            metadata=json.loads(base64.b64decode(packet['associated_data']))
            identities.append((name,metadata['key_epoch'],metadata['sequence_number']))
        def events():
            with engine.connect() as c:
                result=[]
                for name,epoch,sequence in identities:
                    result.extend(c.execute(select(outbox).where(outbox.c.device_id==name,outbox.c.key_epoch==epoch,outbox.c.sequence_number==sequence)).mappings().all())
                return result
        if args.phase=='pending':
            wait(lambda:len(events())==len(identities))
            assert all(e['status'] in ('pending','claimed') for e in events())
            assert all(e['attempts']>=1 for e in events())
            print('PASS: MongoDB unavailable; all accepted events retained in PG outbox with delivery attempts')
        elif args.phase in ('delivered','verify'):
            wait(lambda:len(events())==len(identities) and all(e['status']=='delivered' for e in events()))
            for name,epoch,sequence in identities:
                rows=list(repo.collection.find(dict(device_id=name,key_epoch=epoch,sequence_number=sequence)))
                assert len(rows)==1
            print('PASS: independent histories delivered exactly one document per identity; PG accepted events durable')
        elif args.phase=='replay':
            before=events()
            assert len(before)==len(identities)
            for name,packet in state.items(): publish(name,registry[name],packet)
            time.sleep(2)
            after=events()
            assert [e['id'] for e in before]==[e['id'] for e in after]
            for name,epoch,sequence in identities:
                assert repo.collection.count_documents(dict(device_id=name,key_epoch=epoch,sequence_number=sequence))==1
            print('PASS: replay after receiver/relay restart creates no additional outbox/Mongo records')
        elif args.phase=='identity':
            # Valid AEAD packet for beta, sent under alpha identity to beta topic: broker denies.
            names=list(devices)
            victim=names[1]; sender=names[0]
            sequence=next_sequence('/state/multidevice-sequences.db',victim,registry[victim]['key_epoch'])
            packet=encode_packet(dict(temperature=23,humidity=42,timestamp=datetime.now(timezone.utc).isoformat()),registry,victim,sequence)
            publish(sender,registry[victim],packet)
            time.sleep(2)
            with engine.connect() as c:
                assert c.scalar(select(func.count()).select_from(outbox).where(outbox.c.device_id==victim,outbox.c.sequence_number==sequence))==0
            print('PASS: per-device identity cannot publish another provisioned device topic')
    finally:
        engine.dispose(); repo.close()

if __name__=='__main__': main()

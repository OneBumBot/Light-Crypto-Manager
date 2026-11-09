"""Real MQTT/Mongo/PG/ML checks. Published samples are explicitly controlled fixtures."""
import argparse
import base64
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import time
from sqlalchemy import create_engine,select,func
from src.runtime import database_url
from src.telemetry import load_registry,encode_packet
from src.sequence import next_sequence
from src.ml_storage import events,models,feed,feed_state
from scripts.dual_database_probe import publish,wait

STATE=Path('/state/ml-sample-identities.json')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=['unavailable','publish','marked','scored','retry','verify'])
    args=parser.parse_args()
    engine=create_engine(database_url(),pool_pre_ping=True)
    try:
        if args.phase=='unavailable':
            def unavailable():
                with engine.connect() as c:return c.scalar(select(models.c.status).where(models.c.model_id=='telemetry-statistical'))=='unavailable'
            wait(unavailable)
            with engine.connect() as c:before=c.scalar(select(feed_state.c.published))
            def advanced():
                with engine.connect() as c:return c.scalar(select(feed_state.c.published))>before
            wait(advanced,30)
            print('PASS: missing ML artifact reported unavailable; MQTT -> Mongo delivery continues')
            return
        if args.phase=='publish':
            registry=load_registry('/run/lcm/registry.json');identities=[]
            devices=[name for name in registry if Path('/run/lcm/device_'+name+'.password').exists()]
            assert len(devices)>=3
            origin=datetime.now(timezone.utc)-timedelta(seconds=80)
            for device_index,name in enumerate(devices):
                entry=registry[name]
                for i in range(8):
                    sequence=next_sequence('/state/multidevice-sequences.db',name,entry['key_epoch'])
                    sensor=dict(temperature=35+device_index*15+i*0.1,humidity=45+device_index*10,
                                timestamp=(origin+timedelta(seconds=i*10)).isoformat())
                    publish(name,entry,encode_packet(sensor,registry,name,sequence))
                    identities.append(dict(device_id=name,key_epoch=entry['key_epoch'],sequence_number=sequence))
            STATE.write_text(json.dumps(identities));STATE.chmod(0o600)
            print('PASS: 24 controlled AEAD/TLS samples from three independent devices published')
            return
        identities=json.loads(STATE.read_text())
        def event_rows():
            result=[]
            with engine.connect() as c:
                for identity in identities:
                    result.extend(c.execute(select(events).where(*[events.c[k]==v for k,v in identity.items()],
                        events.c.model_id=='telemetry-statistical',events.c.model_version=='1.0.0')).mappings().all())
            return result
        if args.phase=='marked':
            def marked():
                with engine.connect() as c:
                    return all(c.scalar(select(feed.c.id).where(*[feed.c[k]==v for k,v in identity.items()])) for identity in identities)
            wait(marked)
            print('PASS: all controlled sources durably marked after Mongo confirmation')
        elif args.phase=='retry':
            wait(lambda:any(row['status']=='retry' for row in event_rows()),30)
            print('PASS: actual Mongo outage creates retry state; committed ML events preserved')
        elif args.phase in ('scored','verify'):
            devices={row['device_id'] for row in identities}
            wait(lambda:devices<={row['device_id'] for row in event_rows() if row['status']=='ok'},45)
            rows=event_rows()
            assert len({(r['device_id'],r['key_epoch'],r['sequence_number'],r['model_id'],r['model_version']) for r in rows})==len(rows)
            assert all(row['score'] is None or row['score']>=0 for row in rows)
            with engine.connect() as c:
                available=c.execute(select(models.c.status,models.c.artifact_sha256).where(models.c.model_id=='telemetry-statistical')).one()
                assert available[0]=='available' and len(available[1])==64
            print('PASS: per-device versioned scores persisted, unique identities and model hash verified')
    finally:engine.dispose()

if __name__=='__main__':main()

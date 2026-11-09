"""Real isolated policy/PG/replay checks. No synthetic device acknowledgement."""
import argparse
import base64
from datetime import datetime,timezone
import json
from pathlib import Path
import time
from sqlalchemy import create_engine,select,func
from sqlalchemy.exc import SQLAlchemyError
from src.runtime import database_url
from src.policy.models import decisions,states,signals,versions,worker_status
from src.policy.worker import poll
from src.security_events import journal
from src.telemetry import load_registry
from scripts.dual_database_probe import publish,wait

SNAPSHOT=Path('/state/policy-snapshot.json')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=['replay','snapshot','verify','queued','unavailable'])
    args=parser.parse_args();engine=create_engine(database_url(),pool_pre_ping=True,connect_args={'connect_timeout':2})
    try:
        if args.phase=='unavailable':
            try:poll(engine)
            except SQLAlchemyError:
                snapshot=json.loads(SNAPSHOT.read_text());snapshot['outage_at']=datetime.now(timezone.utc).isoformat()
                SNAPSHOT.write_text(json.dumps(snapshot));SNAPSHOT.chmod(0o600)
                print('PASS: PostgreSQL outage rejects processing; no local fake decision/ACK');return
            raise AssertionError('Expected unavailable PostgreSQL')
        def active():
            with engine.connect() as c:return c.scalar(select(versions.c.version).where(versions.c.active.is_(True)))
        wait(lambda:active() is not None)
        version=active()
        if args.phase=='replay':
            registry=load_registry('/run/lcm/registry.json');packets=json.loads(Path('/state/multidevice-packets.json').read_text())
            for _ in range(3):
                for name,packet in packets.items():publish(name,registry[name],packet)
                time.sleep(1.2)
            def alert():
                with engine.connect() as c:
                    rows=c.execute(select(states).where(states.c.device_id.in_(list(packets)),states.c.version==version)).mappings().all()
                    return len(rows)==len(packets) and all(r['state']['guard']=='ALERT' for r in rows)
            wait(alert)
            name=next(iter(packets));poison=dict(packets[name]);aad=json.loads(base64.b64decode(poison['associated_data']))
            aad['device_id']='spoofed-victim';poison['associated_data']=base64.b64encode(json.dumps(aad).encode()).decode()
            with engine.connect() as c:before=c.scalar(select(func.count()).select_from(journal).where(journal.c.category=='rejected'))
            publish(name,registry[name],poison)
            def rejected():
                with engine.connect() as c:return c.scalar(select(func.count()).select_from(journal).where(journal.c.category=='rejected'))>before
            wait(rejected)
            with engine.connect() as c:
                assert c.scalar(select(func.count()).select_from(states).where(states.c.device_id=='spoofed-victim'))==0
                assert all(d is None for d in c.scalars(select(journal.c.device_id).where(journal.c.category=='rejected')))
            print('PASS: real authenticated replay raises three device risk guards; forged AAD cannot target a victim')
        elif args.phase=='snapshot':
            with engine.connect() as c:
                ids=list(c.scalars(select(decisions.c.id).order_by(decisions.c.created_at).limit(1000)))
                assert ids
            SNAPSHOT.write_text(json.dumps({'ids':ids,'version':version}));SNAPSHOT.chmod(0o600)
            print('PASS: committed bounded decision snapshot persisted')
        elif args.phase=='queued':
            with engine.connect() as c:
                consumed=select(signals.c.event_id).where(signals.c.version==version).scalar_subquery()
                assert c.scalar(select(func.count()).select_from(journal).where(('security:'+journal.c.id).not_in(consumed)))>0
            print('PASS: policy stopped; telemetry keeps running and durable observations remain queued')
        else:
            snapshot=json.loads(SNAPSHOT.read_text())
            def ready():
                with engine.connect() as c:
                    workers=c.execute(select(worker_status)).mappings().all();now=datetime.now(timezone.utc)
                    return any(w['status']=='ready' and (now-w['heartbeat_at']).total_seconds()<15 and (
                        'outage_at' not in snapshot or w['heartbeat_at']>datetime.fromisoformat(snapshot['outage_at'])) for w in workers)
            wait(ready)
            with engine.connect() as c:
                assert set(c.scalars(select(decisions.c.id).where(decisions.c.id.in_(snapshot['ids']))))==set(snapshot['ids'])
                assert c.scalar(select(func.count()).select_from(states).where(states.c.applied.is_not(None)))==0
                assert c.scalar(select(func.count()).select_from(decisions))==c.scalar(select(func.count(func.distinct(decisions.c.event_id))))
            print('PASS: parallel/restarted policy workers retain committed decisions, dedupe sources and never claim applied configuration')
    finally:engine.dispose()

if __name__=='__main__':main()

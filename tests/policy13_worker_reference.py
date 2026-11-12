"""Frozen original poll with explicit test clock; not runtime code."""
"""Optional PG-only DRY_RUN worker. No MQTT, Mongo, model loading or control send."""
import argparse
from datetime import timedelta
import hashlib
import logging
import os
from pathlib import Path
import signal as os_signal
from threading import Event
from sqlalchemy import create_engine,select,func,and_,exists,update
from sqlalchemy.dialects.postgresql import insert
from src.runtime import database_url
from src.security_events import journal,queue
from src.devices import devices
from src.ml_storage import events as ml_events,models as ml_models
from src.policy.models import versions,signals,states,worker_status,intents
from src.policy.signals import Signal,from_ml,utc
from src.policy.rules import Rules
from src.policy.state import install,prune
from policy13_reference import process

log=logging.getLogger(__name__)


def bootstrap(engine):
    with engine.begin() as c:
        # Shared with activation: never overwrite an explicitly selected policy.
        from sqlalchemy import text
        c.execute(text('SELECT pg_advisory_xact_lock(734819207)'))
        if not c.scalar(select(versions.c.version).where(versions.c.active.is_(True))):
            install(c,'default-v1',Rules().payload(),c.scalar(select(func.clock_timestamp())),activate=True)


def poll(engine,prefer_ml=False,*,at=None):
    with engine.begin() as c:
        now=at if at is not None else c.scalar(select(func.clock_timestamp()))
        # Serialize version activation with one bounded processing transaction.
        active=c.execute(select(versions).where(versions.c.active.is_(True)).with_for_update(read=True)).mappings().one()
        version=active['version']
        consumed=exists(select(1).where(signals.c.version==version,signals.c.event_id=='security:'+journal.c.id))
        ml_pending=exists(select(1).where(signals.c.version==version,signals.c.event_id=='ml:'+ml_events.c.id+':'+ml_events.c.status))
        has_ml=prefer_ml and c.scalar(select(ml_events.c.id).where(~ml_pending,ml_events.c.status!='processing').limit(1)) is not None
        row=None if has_ml else c.execute(select(journal).where(~consumed).order_by(journal.c.occurred_at,journal.c.id)
                      .with_for_update(skip_locked=True).limit(1)).mappings().first()
        if row:
            bound=row['device_id'] is not None
            s=Signal('security:'+row['id'],row['source'],row['category'],row['occurred_at'].isoformat(),now.isoformat(),
                row['device_id'],row['key_epoch'],row['sequence_number'],
                'authenticated' if bound else 'unattributed','verified' if bound else 'monitor')
            process(c,s,version,now)
            return True
        identity='ml:'+ml_events.c.id+':'+ml_events.c.status
        consumed=exists(select(1).where(signals.c.version==version,signals.c.event_id==identity))
        row=c.execute(select(ml_events).where(~consumed,ml_events.c.status!='processing')
            .order_by(ml_events.c.available_at,ml_events.c.id).limit(1).with_for_update(skip_locked=True)).mappings().first()
        if row:
            model=c.execute(select(ml_models).where(ml_models.c.model_id==row['model_id'],ml_models.c.model_version==row['model_version'])).mappings().first()
            try:
                if model is None:raise ValueError('Missing model registry')
                s=from_ml(row,model,now)
                # Only device registry bindings, never a claimed device ID from raw input.
                if not c.scalar(select(devices.c.device_id).where(devices.c.device_id==s.device_id,devices.c.key_epoch==s.key_epoch,devices.c.enabled.is_(True))):
                    raise ValueError('Device binding unavailable')
                process(c,s,version,now)
            except ValueError:
                c.execute(insert(signals).values(event_id='ml:'+row['id']+':'+row['status'],version=version,
                    source='ml',payload={'diagnostic':'SourceContractRejected'},status='rejected',created_at=now).on_conflict_do_nothing())
            return True
        rules=Rules.parse(active['config'])
        # One degradation decision per telemetry expiry, not a periodic stream of identical decisions.
        row=c.execute(select(states).where(states.c.version==version,states.c.observed_risk!='UNKNOWN')
            .order_by(states.c.updated_at).limit(128).with_for_update(skip_locked=True)).mappings().all()
        for item in row:
            state=item['state'];last=state.get('last_telemetry_at')
            ml_stale=state.get('ml_available') and state.get('last_ml_at') and (now-utc(state['last_ml_at'])).total_seconds()>rules.ml_fresh_seconds
            if ml_stale:
                eid=hashlib.sha256((item['device_id']+version+state['last_ml_at']+'ml').encode()).hexdigest()
                s=Signal('ml-stale:'+eid,'system','unavailable',now.isoformat(),now.isoformat(),item['device_id'],
                    binding='authenticated',trust='monitor',original={'component':'ml'})
                if process(c,s,version,now):return True
            if last and (now-utc(last)).total_seconds()>max(rules.telemetry_fresh_seconds,rules.cooldown_seconds) and (
                not state.get('last_decision_at') or (now-utc(state['last_decision_at'])).total_seconds()>rules.min_decision_seconds):
                eid=hashlib.sha256((item['device_id']+version+last).encode()).hexdigest()
                s=Signal('stale:'+eid,'system','stale',now.isoformat(),now.isoformat(),item['device_id'],
                    binding='authenticated',trust='monitor')
                if process(c,s,version,now):return True
        # Expired proposals remain visible and are never treated as acknowledged/applied.
        old=c.execute(select(intents).where(intents.c.status=='proposed').limit(128).with_for_update(skip_locked=True)).mappings().all()
        for item in old:
            if utc(item['command']['expires_at'])<=now:
                c.execute(update(intents).where(intents.c.id==item['id']).values(status='expired'))
        return False


def heartbeat(engine,status='ready',diagnostic=None):
    with engine.begin() as c:
        now=c.scalar(select(func.clock_timestamp()))
        c.execute(insert(worker_status).values(worker_id=os.environ.get('HOSTNAME','policy-worker'),status=status,
            mode='DRY_RUN',heartbeat_at=now,diagnostic=diagnostic).on_conflict_do_update(index_elements=['worker_id'],
            set_=dict(status=status,mode='DRY_RUN',heartbeat_at=now,diagnostic=diagnostic)))


def prune_journal(c,days,now):
    if type(days) is not int or days<1:raise ValueError('Positive retention days required')
    q=c.execute(select(queue).where(queue.c.id==1).with_for_update()).mappings().first()
    if q is None:return 0
    version=c.scalar(select(versions.c.version).where(versions.c.active.is_(True)))
    consumed=exists(select(1).where(signals.c.version==version,signals.c.event_id=='security:'+journal.c.id))
    ids=list(c.scalars(select(journal.c.id).where(consumed,journal.c.occurred_at<now-timedelta(days=days))
        .limit(1000).with_for_update(skip_locked=True)))
    if ids:
        c.execute(journal.delete().where(journal.c.id.in_(ids)))
        c.execute(update(queue).where(queue.c.id==1).values(retained=queue.c.retained-len(ids)))
    return len(ids)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once',action='store_true');parser.add_argument('--prune-days',type=int)
    args=parser.parse_args();logging.basicConfig(level=logging.INFO)
    ready=Path('/tmp/policy-ready');ready.unlink(missing_ok=True)
    engine=create_engine(database_url(),pool_pre_ping=True,connect_args={'connect_timeout':3,'options':'-cstatement_timeout=5000 -clock_timeout=2000'},pool_timeout=5)
    stop=Event()
    for sig in [os_signal.SIGINT,os_signal.SIGTERM]:os_signal.signal(sig,lambda *_:stop.set())
    try:
        if args.prune_days is not None:
            with engine.begin() as c:
                now=c.scalar(select(func.clock_timestamp()))
                print('Explicitly pruned:',prune(c,args.prune_days,now),prune_journal(c,args.prune_days,now))
            return
        batch=int(os.environ.get('POLICY_BATCH_SIZE','32'))
        if not 1<=batch<=128:raise ValueError('Policy batch bound')
        if os.environ.get('POLICY_MODE','DRY_RUN')!='DRY_RUN':raise ValueError('Only DRY_RUN worker is supported')
        while not stop.is_set():
            try:
                bootstrap(engine)
                for index in range(batch):
                    if stop.is_set() or not poll(engine,prefer_ml=bool(index%2)):break
                heartbeat(engine);ready.touch()
            except Exception as e:
                ready.unlink(missing_ok=True);log.warning('Policy unavailable (%s)',type(e).__name__)
                try:heartbeat(engine,'unavailable',type(e).__name__[:80])
                except Exception:pass
            if args.once:break
            stop.wait(1)
    finally:
        ready.unlink(missing_ok=True);engine.dispose()

if __name__=='__main__':main()

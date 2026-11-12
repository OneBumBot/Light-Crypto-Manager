"""Optional PG-only DRY_RUN worker. No MQTT, Mongo, model loading or control send."""
import argparse
from datetime import datetime,timezone,timedelta
import hashlib
import logging
import os
from pathlib import Path
import signal as os_signal
import time
from threading import Event
from sqlalchemy import create_engine,select,func,and_,exists,update
from sqlalchemy.dialects.postgresql import insert
from src.runtime import database_url
from src.security_events import journal,queue
from src.devices import devices
from src.ml_storage import events as ml_events,models as ml_models
from .models import versions,signals,states,worker_status,intents
from .signals import Signal,from_ml,utc
from .rules import Rules
from .state import install,process,prune

log=logging.getLogger(__name__)


def bootstrap(engine):
    with engine.begin() as c:
        # Shared with activation: never overwrite an explicitly selected policy.
        from sqlalchemy import text
        c.execute(text('SELECT pg_advisory_xact_lock(734819207)'))
        if not c.scalar(select(versions.c.version).where(versions.c.active.is_(True))):
            install(c,'default-v1',Rules().payload(),c.scalar(select(func.clock_timestamp())),activate=True)


def poll(engine,prefer_ml=False):
    """Compatible one-event entrypoint; runtime uses bounded transactions."""
    return bool(poll_batch(engine,limit=1,prefer_ml=prefer_ml))


def poll_batch(engine,limit=32,prefer_ml=None,*,at=None,before_commit=None,after_claim=None,maintenance=True):
    from time import monotonic
    from sqlalchemy import text,delete
    from .models import pending,schedule
    from .state import BatchRules
    if type(limit) is not int or not 1<=limit<=32:raise ValueError('Policy transaction bound')
    if prefer_ml is not None and type(prefer_ml) is not bool:raise ValueError('Policy scheduling preference')
    with engine.begin() as c:
        # Same lock as install and prune, never taken by source admission.
        c.execute(text('SELECT pg_advisory_xact_lock(734819207)'))
        active=c.execute(select(versions).where(versions.c.active.is_(True))).mappings().one()
        version=active['version'];context=BatchRules(version,Rules.parse(active['config']))
        turn=c.execute(select(schedule.c.next_ml).where(schedule.c.id==1).with_for_update()).scalar_one() if prefer_ml is None else prefer_ml
        clock=lambda:utc(at() if callable(at) else at) if at is not None else c.scalar(select(func.clock_timestamp()))
        batches={kind:list(c.execute(select(pending).where(pending.c.kind==kind)
            .order_by(pending.c.sort_at,pending.c.event_id).limit(limit).with_for_update()).mappings()) for kind in ['security','ml']}
        if after_claim:after_claim()
        positions={'security':0,'ml':0};count=0;started=monotonic()
        for index in range(limit):
            preferred='ml' if bool(index%2)!=bool(turn) else 'security'
            kind=preferred if positions[preferred]<len(batches[preferred]) else ('security' if preferred=='ml' else 'ml')
            if positions[kind]>=len(batches[kind]):break
            item=batches[kind][positions[kind]];positions[kind]+=1;row=item['payload'];now=clock()
            if kind=='security':
                bound=row['device_id'] is not None
                signal=Signal(item['event_id'],row['source'],row['category'],row['occurred_at'],now.isoformat(),
                    row['device_id'],row['key_epoch'],row['sequence_number'],
                    'authenticated' if bound else 'unattributed','verified' if bound else 'monitor')
                process(c,signal,version,now,batch_rules=context)
            else:
                model=c.execute(select(ml_models).where(ml_models.c.model_id==row['model_id'],ml_models.c.model_version==row['model_version'])).mappings().first()
                try:
                    if model is None:raise ValueError('Missing model registry')
                    signal=from_ml(row,model,now)
                    if not c.scalar(select(devices.c.device_id).where(devices.c.device_id==signal.device_id,devices.c.key_epoch==signal.key_epoch,devices.c.enabled.is_(True))):raise ValueError('Device binding unavailable')
                    process(c,signal,version,now,batch_rules=context)
                except ValueError:
                    c.execute(insert(signals).values(event_id=item['event_id'],version=version,source='ml',payload={'diagnostic':'SourceContractRejected'},status='rejected',created_at=now).on_conflict_do_nothing())
            c.execute(delete(pending).where(pending.c.event_id==item['event_id']))
            count+=1
            # Soft wall-time bound between events; DB statement/lock deadlines
            # still apply to individual statements. Never abandon partial work.
            if monotonic()-started>=.25:break
        if count:c.execute(update(schedule).where(schedule.c.id==1).values(next_ml=bool(turn)!=bool(count%2)))
        if maintenance:
            count+=int(bool(_maintenance(c,context.rules,version,clock(),context)))
        if before_commit:before_commit()
        return count


def _maintenance(c,rules,version,now,context):
    from .models import pending
    waiting=exists(select(1).where(pending.c.payload['device_id'].astext==states.c.device_id))
    # One degradation decision per telemetry expiry, not a periodic stream of identical decisions.
    row=c.execute(select(states).where(states.c.version==version,states.c.observed_risk!='UNKNOWN',~waiting)
        .order_by(states.c.updated_at).limit(128).with_for_update(skip_locked=True)).mappings().all()
    for item in row:
        state=item['state'];last=state.get('last_telemetry_at')
        ml_stale=state.get('ml_available') and state.get('last_ml_at') and (now-utc(state['last_ml_at'])).total_seconds()>rules.ml_fresh_seconds
        if ml_stale:
            eid=hashlib.sha256((item['device_id']+version+state['last_ml_at']+'ml').encode()).hexdigest()
            s=Signal('ml-stale:'+eid,'system','unavailable',now.isoformat(),now.isoformat(),item['device_id'],
                binding='authenticated',trust='monitor',original={'component':'ml'})
            if process(c,s,version,now,batch_rules=context):return True
        if last and (now-utc(last)).total_seconds()>max(rules.telemetry_fresh_seconds,rules.cooldown_seconds) and (
            not state.get('last_decision_at') or (now-utc(state['last_decision_at'])).total_seconds()>rules.min_decision_seconds):
            eid=hashlib.sha256((item['device_id']+version+last).encode()).hexdigest()
            s=Signal('stale:'+eid,'system','stale',now.isoformat(),now.isoformat(),item['device_id'],
                binding='authenticated',trust='monitor')
            if process(c,s,version,now,batch_rules=context):return True
    # Expired proposals remain visible and are never treated as acknowledged/applied.
    old=c.execute(select(intents).where(intents.c.status=='proposed').limit(128).with_for_update(skip_locked=True)).mappings().all()
    for item in old:
        if utc(item['command']['expires_at'])<=now:
            c.execute(update(intents).where(intents.c.id==item['id']).values(status='expired'))
    return False


def heartbeat(engine,status='ready',diagnostic=None,metrics=None):
    with engine.begin() as c:
        now=c.scalar(select(func.clock_timestamp()))
        c.execute(insert(worker_status).values(worker_id=os.environ.get('HOSTNAME','policy-worker'),status=status,
            mode='DRY_RUN',heartbeat_at=now,diagnostic=diagnostic,metrics=metrics or {}).on_conflict_do_update(index_elements=['worker_id'],
            set_=dict(status=status,mode='DRY_RUN',heartbeat_at=now,diagnostic=diagnostic,metrics=metrics or {})))


def prune_journal(c,days,now):
    if type(days) is not int or days<1:raise ValueError('Positive retention days required')
    from sqlalchemy import text
    c.execute(text('SELECT pg_advisory_xact_lock(734819207)'))
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
        bootstrapped=False;total=0;polls=0;last_success=None;last_maintenance=0;retries=0
        while not stop.is_set():
            count=0
            try:
                if not bootstrapped:bootstrap(engine);bootstrapped=True
                started=time.perf_counter();maintain=time.monotonic()-last_maintenance>=5
                count=poll_batch(engine,limit=min(batch,32),maintenance=maintain);elapsed=time.perf_counter()-started
                if maintain:last_maintenance=time.monotonic()
                total+=count;polls+=1
                if count:last_success=datetime.now(timezone.utc).isoformat()
                heartbeat(engine,metrics=dict(processed_total=total,polls_total=polls,last_batch_count=count,last_batch_seconds=elapsed,last_successful_processing_at=last_success,transaction_max_source_events=32,retries_total=retries));ready.touch()
            except Exception as e:
                count=0
                retries+=1
                ready.unlink(missing_ok=True);log.warning('Policy unavailable (%s)',type(e).__name__)
                try:heartbeat(engine,'unavailable',type(e).__name__[:80])
                except Exception:pass
            if args.once:break
            stop.wait(.01 if count else 1)
    finally:
        ready.unlink(missing_ok=True);engine.dispose()

if __name__=='__main__':main()

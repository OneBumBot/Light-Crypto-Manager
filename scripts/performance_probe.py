"""Bounded read-only authoritative performance snapshots/export, no fake telemetry."""
import argparse,json,time,sys
from datetime import datetime
from sqlalchemy import create_engine,select,func,text
from src.runtime import database_url
from src.outbox import outbox,metrics
from src.device_control import models as m
from src.device_control.config import load
from src.policy.models import worker_status,states
from src.mongo_repository import MongoRepository
from pymongo.errors import PyMongoError


def snapshot(engine):
    with engine.connect() as c:
        result=dict(checked_at=c.scalar(select(func.clock_timestamp())).isoformat(),
            devices=[dict(r) for r in c.execute(select(m.devices.c.device_id,m.devices.c.effective_profile,m.devices.c.effective_event,m.devices.c.sequence_reserved,m.devices.c.command_sequence)).mappings()],
            per_device={r.device_id:dict(count=r.n,last_sequence=r.seq) for r in c.execute(select(outbox.c.device_id,func.count().label('n'),func.max(outbox.c.sequence_number).label('seq')).group_by(outbox.c.device_id))},
            outbox={k:int(v) for k,v in c.execute(select(outbox.c.status,func.count()).group_by(outbox.c.status))},
            counters={k:int(v) for k,v in c.execute(select(metrics.c.kind,func.sum(metrics.c.count)).group_by(metrics.c.kind))},
            transitions=c.scalar(select(func.count()).select_from(m.transitions)),completed=c.scalar(select(func.count()).select_from(m.transitions).where(m.transitions.c.phase=='EFFECTIVE_CONFIRMED')),
            unknown=c.scalar(select(func.count()).select_from(m.transitions).where(m.transitions.c.phase.in_(['UNKNOWN_OUTCOME','RECOVERY_REQUIRED']))),
            authenticated_ack=c.scalar(select(func.count()).select_from(m.acks)),receipts=c.scalar(select(func.count()).select_from(m.evidence)),
            policy_modes=list(c.scalars(select(worker_status.c.mode).distinct())),policy_applied=c.scalar(select(func.count()).select_from(states).where(states.c.applied.is_not(None))),
            pg_connections=c.scalar(text('SELECT count(*) FROM pg_stat_activity WHERE datname=current_database()')),
            database_bytes=c.scalar(text('SELECT pg_database_size(current_database())')),
            pg_stats=dict(c.execute(text('SELECT xact_commit,xact_rollback,deadlocks FROM pg_stat_database WHERE datname=current_database()')).mappings().one()),
            migration=c.scalar(text('SELECT version_num FROM alembic_version')),ml_trusted=False)
    repo=MongoRepository('relay')
    try:result['mongo_managed']=repo.collection.count_documents({'device_id':{'$in':list(load())}},maxTimeMS=2000)
    except PyMongoError:result['mongo_managed']=None
    finally:repo.close()
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['snapshot','export','plans','transitions','storage','monitoring-plans','watermark','policy-diagnostics']);a=p.parse_args()
    engine=create_engine(database_url(),connect_args={'connect_timeout':2})
    try:
        if a.action=='snapshot':print(json.dumps(snapshot(engine),indent=2));return
        if a.action=='policy-diagnostics':
            from src.policy import models as policy
            from src.security_events import journal,queue
            with engine.connect() as c:
                version=c.scalar(select(policy.versions.c.version).where(policy.versions.c.active.is_(True)))
                total=c.scalar(select(func.count()).select_from(journal))
                consumed=c.scalar(select(func.count()).select_from(policy.signals).where(policy.signals.c.version==version,policy.signals.c.event_id.like('security:%')))
                lag=c.scalar(select(policy.decisions.c.source_lag_seconds).order_by(policy.decisions.c.created_at.desc()).limit(1))
                capacity=dict(c.execute(select(queue)).mappings().one())
                q=select(journal.c.id).where(~select(1).where(policy.signals.c.version==version,policy.signals.c.event_id=='security:'+journal.c.id).exists()).order_by(journal.c.occurred_at,journal.c.id).limit(1)
                plan=c.execute(text('EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) '+str(q.compile(c,compile_kwargs={'literal_binds':True})))).scalar()
            print(json.dumps(dict(active_version=version,observations=total,consumed=consumed,pending_observations=total-consumed,last_processed_source_lag_seconds=lag,capacity=capacity,actual_pending_select_plan=plan)));return
        if a.action=='monitoring-plans':
            from sqlalchemy import event
            from src.web.monitoring import snapshot as monitoring_snapshot
            captured=[]
            def capture(conn,cursor,statement,parameters,context,executemany):
                if statement.startswith('SELECT'):captured.append((statement,parameters))
            event.listen(engine,'before_cursor_execute',capture)
            with engine.connect() as c:monitoring_snapshot(c,device='alpha')
            event.remove(engine,'before_cursor_execute',capture)
            plans=[]
            with engine.begin() as c:
                c.execute(text('SET LOCAL statement_timeout=10000'))
                for statement,parameters in captured:
                    plan=c.exec_driver_sql('EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) '+statement,parameters).scalar()
                    plans.append(dict(sql=statement,plan=plan))
            print(json.dumps(dict(query_count=len(captured),plans=plans)));return
        if a.action=='transitions':
            with engine.connect() as c:
                rows=[dict(r) for r in c.execute(select(m.transitions).order_by(m.transitions.c.created_at).limit(100)).mappings()]
                commands=[dict(r) for r in c.execute(select(m.commands.c.id,m.commands.c.transition_id,m.commands.c.phase,m.commands.c.status,m.commands.c.attempts,m.commands.c.available_at).limit(200)).mappings()]
            print(json.dumps(dict(transitions=rows,commands=commands),default=lambda v:v.isoformat()));return
        if a.action=='storage':
            repo=MongoRepository('relay')
            try:
                print(json.dumps(dict(indexes=repo.collection.index_information(),history_explain=repo.collection.database.command('explain',{'find':repo.collection.name,'filter':{'device_id':'alpha'},'sort':{'measured_at':-1,'_id':-1},'limit':50},verbosity='executionStats')),default=str))
            finally:repo.close()
            return
        args=json.load(sys.stdin)
        if a.action=='watermark':
            cutoff=datetime.fromisoformat(args['before'])
            with engine.connect() as c:
                pending=c.scalar(select(func.count()).select_from(outbox).where(outbox.c.created_at<=cutoff,outbox.c.status!='delivered'))
            print(json.dumps(dict(pending_before_watermark=pending)));return
        if a.action=='export':
            start=datetime.fromisoformat(args['start']);end=datetime.fromisoformat(args['end'])
            with engine.connect() as c:
                rows=[dict(r) for r in c.execute(select(outbox.c.id,outbox.c.device_id,outbox.c.key_epoch,outbox.c.sequence_number,outbox.c.created_at,outbox.c.delivered_at,outbox.c.status,outbox.c.attempts,outbox.c.payload).where(outbox.c.created_at>=start,outbox.c.created_at<=end).order_by(outbox.c.device_id,outbox.c.sequence_number).limit(100001)).mappings()]
                if len(rows)>100000:raise ValueError('Bounded export exceeded')
            for r in rows:
                for k in ['created_at','delivered_at']:
                    if r[k]:r[k]=r[k].isoformat()
            print(json.dumps(dict(rows=rows,snapshot=snapshot(engine))));return
        queries={
            'pending_count':"SELECT count(*) FROM telemetry_outbox WHERE status != 'delivered'",
            'latest_distinct':"SELECT DISTINCT ON (device_id) device_id,id,created_at FROM telemetry_outbox ORDER BY device_id,created_at DESC",
            'replay_lookup':"SELECT * FROM mqtt_replay_state WHERE consumer='receiver' AND device_id='alpha' AND key_epoch=1",
            'control_lock':"SELECT * FROM live_control_devices WHERE device_id='alpha' FOR UPDATE",
            'outbox_claim':"SELECT id FROM telemetry_outbox WHERE status='pending' AND available_at<=now() ORDER BY available_at,id LIMIT 1",
            'policy_pending':"SELECT id FROM security_observations ORDER BY occurred_at,id LIMIT 1",
            'transition_history':"SELECT id FROM live_control_transitions WHERE device_id='alpha' ORDER BY created_at DESC LIMIT 20"}
        plans={}
        with engine.begin() as c:
            c.execute(text('SET LOCAL statement_timeout=10000'))
            for name,q in queries.items():plans[name]=c.execute(text('EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) '+q)).scalar()
        print(json.dumps(plans))
    finally:engine.dispose()

if __name__=='__main__':main()

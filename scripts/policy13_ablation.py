"""Matched-input algorithm ablation in disposable schemas, not MQTT admission evidence."""
import argparse,json,uuid,time,sys,hashlib,resource
from pathlib import Path
from datetime import datetime,timezone,timedelta
from sqlalchemy import create_engine,text,select,func,event
from sqlalchemy.engine import make_url
from src.runtime import database_url
from src.migrate import upgrade
from src.policy import models as m
from src.policy.rules import Rules
from src.policy.worker import poll_batch
from src.policy.state import install
from src.security_events import journal,queue
sys.path.insert(0,'tests')
from policy13_worker_reference import poll as sequential
from src.web.models import db
from src.replay import metadata as replay_metadata
T=datetime(2026,1,1,tzinfo=timezone.utc)


def run(admin,case):
    schema='p13ablation_'+uuid.uuid4().hex
    with admin.begin() as c:c.execute(text('CREATE SCHEMA '+schema))
    url=make_url(database_url()).update_query_dict({'options':'-csearch_path='+schema})
    e=create_engine(url);count=1000;stats=dict(sql_count=0,sql_seconds=0.,commits=0,rollbacks=0,transaction_seconds=[]);txstart={}
    try:
        db.metadata.create_all(e);replay_metadata.create_all(e);upgrade(e)
        with e.begin() as c:
            install(c,'ablation-v1',Rules().payload(),T,activate=True)
            values=[dict(id=str(uuid.UUID(int=n+1)),source='protocol',category='accepted',device_id='dev'+str(n%10),key_epoch=1,sequence_number=n+1,occurred_at=T+timedelta(microseconds=n)) for n in range(2000)]
            c.execute(journal.insert(),values);c.execute(queue.insert().values(id=1,retained=2000))
            c.execute(m.signals.insert(),[dict(event_id='security:'+v['id'],version='ablation-v1',device_id=v['device_id'],source='protocol',payload={'retained_identity':True},status='accepted',created_at=T) for v in values[:1000]])
            c.execute(m.pending.delete().where(m.pending.c.source_id.in_([v['id'] for v in values[:1000]])))
        def before(c,cursor,statement,params,context,many):context._p13=time.perf_counter()
        def after(c,cursor,statement,params,context,many):stats['sql_count']+=1;stats['sql_seconds']+=time.perf_counter()-context._p13
        def begin(c):txstart[id(c)]=time.perf_counter()
        def commit(c):stats['commits']+=1;stats['transaction_seconds'].append(time.perf_counter()-txstart.pop(id(c),time.perf_counter()))
        def rollback(c):stats['rollbacks']+=1
        listeners=[('before_cursor_execute',before),('after_cursor_execute',after),('begin',begin),('commit',commit),('rollback',rollback)]
        for name,callback in listeners:event.listen(e,name,callback)
        start=time.perf_counter();cpu=time.process_time();n=0
        while n<count:
            if case in ['legacy_sleep','legacy_no_sleep']:
                for index in range(min(32,count-n)):
                    assert sequential(e,prefer_ml=bool(index%2),at=T+timedelta(seconds=100));n+=1
                if case=='legacy_sleep' and n<count:time.sleep(1)
            else:
                n+=poll_batch(e,limit=1 if case=='queue_single' else 32,at=T+timedelta(seconds=100),maintenance=False)
                if n<count:time.sleep(1 if case=='queue_batch_sleep' else .01 if case=='queue_batch_adaptive' else 0)
            if time.perf_counter()-start>180:raise TimeoutError('Bounded ablation run')
        seconds=time.perf_counter()-start;cpu_seconds=time.process_time()-cpu
        for name,callback in listeners:event.remove(e,name,callback)
        with e.connect() as c:
            state=[dict(v) for v in c.execute(select(m.states).order_by(m.states.c.device_id)).mappings()]
            assert c.scalar(select(func.count()).select_from(m.signals))==2000
            fsm_hash=hashlib.sha256(json.dumps(state,default=lambda v:v.isoformat(),sort_keys=True).encode()).hexdigest()
        return dict(case=case,input=1000,initial_consumed_history=1000,seconds=seconds,events_per_second=count/seconds,cpu_seconds=cpu_seconds,stats=stats,final_fsm_sha256=fsm_hash,per_event_clock=(T+timedelta(seconds=100)).isoformat(),evaluation_clock_injected=True)
    finally:
        e.dispose()
        with admin.begin() as c:c.execute(text('DROP SCHEMA '+schema+' CASCADE'))


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',default='-');a=p.parse_args();admin=create_engine(database_url());runs=[];names=['legacy_sleep','legacy_no_sleep','queue_single','queue_batch_sleep','queue_batch_adaptive']
    for repeat in range(3):
        for case in names[repeat:]+names[:repeat]:runs.append(dict(repeat=repeat,**run(admin,case)))
    assert len({v['final_fsm_sha256'] for v in runs})==1
    report=dict(scope='private synthetic matched-input/controller comparison, common0011 schema; not MQTT telemetry',runs=runs,commit_time_boundary='event listener before DBAPI commit excludes final fsync; wall time includes it',exit_code=0)
    data=json.dumps(report,indent=2)
    if a.output=='-':print(data)
    else:Path(a.output).write_text(data)
    admin.dispose()
if __name__=='__main__':main()

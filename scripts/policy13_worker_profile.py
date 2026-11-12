"""Lab-only bounded SQL/poll instrumentation, no SQL parameters or source payload logs."""
import json,time,os
from collections import deque
from pathlib import Path
from sqlalchemy import event
from sqlalchemy.engine import Engine
from src.policy import worker

metrics=dict(sql_count=0,sql_seconds=0.,commits=0,rollbacks=0,processed=0,polls=0)
recent={k:deque(maxlen=1024) for k in ['poll_seconds','process_seconds','transaction_seconds']}
@event.listens_for(Engine,'before_cursor_execute')
def before(c,cursor,statement,parameters,context,many):context._p13_start=time.perf_counter()
@event.listens_for(Engine,'after_cursor_execute')
def after(c,cursor,statement,parameters,context,many):
    metrics['sql_count']+=1;metrics['sql_seconds']+=time.perf_counter()-context._p13_start
@event.listens_for(Engine,'begin')
def begin(c):c.info['_p13_begin']=time.perf_counter()
@event.listens_for(Engine,'commit')
def commit(c):
    metrics['commits']+=1;recent['transaction_seconds'].append(time.perf_counter()-c.info.pop('_p13_begin',time.perf_counter()))
@event.listens_for(Engine,'rollback')
def rollback(c):metrics['rollbacks']+=1

def wrap(name,series):
    original=getattr(worker,name)
    def measured(*args,**kw):
        delay=int(os.environ.get('POLICY13_TEST_DELAY_MS','0')) if name=='poll_batch' else 0
        if not 0<=delay<=1000 or (delay and os.environ.get('APP_ENV')!='test'):raise ValueError('Explicit bounded lab-only delay')
        if delay:time.sleep(delay/1000)
        start=time.perf_counter()
        try:
            result=original(*args,**kw)
            if name=='process':metrics['processed']+=1
            else:metrics['polls']+=1
            return result
        finally:recent[series].append(time.perf_counter()-start)
    setattr(worker,name,measured)
wrap('process','process_seconds')
wrap('poll','poll_seconds')
if hasattr(worker,'poll_batch'):wrap('poll_batch','poll_seconds')
original=worker.heartbeat

def heartbeat(*args,**kw):
    result=original(*args,**kw)
    Path('/tmp/policy-cost.json').write_text(json.dumps(dict(**metrics,recent={k:list(v) for k,v in recent.items()},transaction_boundary='SQLAlchemy commit event precedes DBAPI commit; excludes final fsync latency')))
    return result
worker.heartbeat=heartbeat
if __name__=='__main__':worker.main()

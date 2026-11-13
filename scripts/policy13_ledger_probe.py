"""Independent post-run source/marker/Outbox/Mongo census, bounded and read-only."""
import json
from sqlalchemy import create_engine,text
from src.runtime import database_url
from src.mongo_repository import MongoRepository
from scripts.performance_probe import snapshot
from src.device_control.config import load


def main():
    e=create_engine(database_url());r=snapshot(e)
    with e.connect() as c:
        r['source_rows']=[dict(v) for v in c.execute(text("SELECT o.id,o.device_id,o.key_epoch,o.sequence_number,o.category,o.occurred_at,p.created_at AS processed_at,p.status,p.version FROM security_observations o LEFT JOIN policy_signals p ON p.event_id='security:'||o.id AND p.version=(SELECT version FROM policy_versions WHERE active) ORDER BY o.occurred_at,o.id LIMIT 100000")).mappings()]
        r['outbox_rows']=[dict(v) for v in c.execute(text('SELECT id,device_id,key_epoch,sequence_number,payload,created_at,delivered_at,status FROM telemetry_outbox ORDER BY created_at,id LIMIT 100000')).mappings()]
        r['actual_query_plans']={'baseline_full_row':c.scalar(text("EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) SELECT o.* FROM security_observations o WHERE NOT EXISTS(SELECT 1 FROM policy_signals s WHERE s.version=(SELECT version FROM policy_versions WHERE active) AND s.event_id='security:'||o.id) ORDER BY o.occurred_at,o.id LIMIT 1 FOR UPDATE SKIP LOCKED"))}
        if c.scalar(text("SELECT to_regclass('policy_pending')")):
            r['actual_query_plans']['optimized_full_row']=c.scalar(text("EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) SELECT * FROM policy_pending WHERE kind='security' ORDER BY sort_at,event_id LIMIT 32 FOR UPDATE"))
        r['source_count']=c.scalar(text('SELECT count(*) FROM security_observations'))
        r['capacity']=dict(c.execute(text('SELECT * FROM security_observation_capacity')).mappings().one())
        r['duplicate_markers']=c.scalar(text('SELECT count(*) FROM(SELECT event_id,version FROM policy_signals GROUP BY event_id,version HAVING count(*)>1)t'))
        r['duplicate_decisions']=c.scalar(text('SELECT count(*) FROM(SELECT event_id,version FROM policy_decisions GROUP BY event_id,version HAVING count(*)>1)t'))
        r['policy_profiles']=[dict(v) for v in c.execute(text('SELECT version,sha256,config,active FROM policy_versions ORDER BY version')).mappings()]
        r['source_counts_by_status']=[dict(v) for v in c.execute(text("SELECT status,count(*) AS n FROM policy_signals WHERE event_id LIKE 'security:%' GROUP BY status")).mappings()]
    repo=MongoRepository('relay')
    try:
        r['mongo_rows']=[{k:v for k,v in row.items() if k!='_id'} for row in repo.collection.find({'device_id':{'$in':list(load())}},dict(_id=0,device_id=1,key_epoch=1,sequence_number=1,crypto_profile=1)).limit(100000).max_time_ms(5000)]
    finally:repo.close()
    assert len(r['source_rows'])==r['source_count']==r['capacity']['retained']
    assert r['capacity']['overflow']==0
    assert len(r['outbox_rows'])==r['counters'].get('accepted',0)==len(r['mongo_rows'])
    assert r['duplicate_markers']==r['duplicate_decisions']==r['policy_applied']==r['transitions']==0
    r['exit_code']=0;print(json.dumps(r,default=lambda v:v.isoformat() if hasattr(v,'isoformat') else float(v)));e.dispose()
if __name__=='__main__':main()

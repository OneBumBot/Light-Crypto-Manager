"""Bounded Stage13 SQL observations, with source identities and diagnostic outcomes."""
import argparse,json
from datetime import datetime
from sqlalchemy import create_engine,text
from src.runtime import database_url


def snapshot(c):
    result=dict(c.execute(text("SELECT clock_timestamp() AS at,version,sha256 FROM policy_versions WHERE active")).mappings().one());v=result['version']
    query="""SELECT count(*) AS total,count(*) FILTER(WHERE p.event_id IS NOT NULL) AS consumed,
    count(*) FILTER(WHERE p.event_id IS NULL) AS pending,
    extract(epoch FROM clock_timestamp()-min(o.occurred_at) FILTER(WHERE p.event_id IS NULL)) AS oldest_pending_age
    FROM security_observations o LEFT JOIN policy_signals p ON p.event_id='security:'||o.id AND p.version=:v"""
    result['security']=dict(c.execute(text(query),dict(v=v)).mappings().one())
    result['ml_pending']=c.scalar(text("SELECT count(*) FROM ml_anomaly_events m WHERE m.status!='processing' AND NOT EXISTS(SELECT 1 FROM policy_signals p WHERE p.version=:v AND p.event_id='ml:'||m.id||':'||m.status)"),dict(v=v))
    result['signals']=dict(c.execute(text('SELECT status,count(*) FROM policy_signals WHERE version=:v GROUP BY status'),dict(v=v)).all())
    result['sources']=dict(c.execute(text('SELECT source,count(*) FROM policy_signals WHERE version=:v GROUP BY source'),dict(v=v)).all())
    result['last_processed']=dict(c.execute(text("SELECT max(created_at) AS at,max((payload->>'occurred_at')::timestamptz) AS evidence_at FROM policy_signals WHERE version=:v AND event_id LIKE 'security:%'"),dict(v=v)).mappings().one())
    for name,table in [('decisions','policy_decisions'),('transitions','policy_transitions')]:result[name]=c.scalar(text(f'SELECT count(*) FROM {table} WHERE version=:v'),dict(v=v))
    result['intents']=dict(c.execute(text('SELECT status,count(*) FROM policy_control_intents GROUP BY status')).all())
    result['capacity']=dict(c.execute(text('SELECT * FROM security_observation_capacity')).mappings().one())
    result['db']=dict(c.execute(text("SELECT numbackends,xact_commit,xact_rollback,deadlocks FROM pg_stat_database WHERE datname=current_database()")).mappings().one())
    result['lock_waits']=c.scalar(text("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock'"))
    result['admission']=dict(c.execute(text('SELECT kind,sum(count) FROM ingestion_metrics GROUP BY kind')).all())
    result['outbox']=dict(c.execute(text('SELECT status,count(*) FROM telemetry_outbox GROUP BY status')).all())
    result['worker']=[dict(r) for r in c.execute(text('SELECT * FROM policy_worker_status ORDER BY heartbeat_at DESC LIMIT 4')).mappings()]
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['snapshot','schema','export']);a=p.parse_args();e=create_engine(database_url())
    with e.connect() as c:
        if a.action=='snapshot':r=snapshot(c)
        elif a.action=='schema':
            r=dict(server_version=c.scalar(text('SELECT version()')),sqlalchemy_version=__import__('sqlalchemy').__version__,python_version=__import__('platform').python_version(),migration=c.scalar(text('SELECT version_num FROM alembic_version')),columns=[dict(v) for v in c.execute(text("SELECT table_name,column_name,data_type,is_nullable FROM information_schema.columns WHERE table_schema=current_schema() ORDER BY table_name,ordinal_position")).mappings()],indexes=[dict(v) for v in c.execute(text("SELECT tablename,indexname,indexdef FROM pg_indexes WHERE schemaname=current_schema() ORDER BY tablename,indexname")).mappings()],settings=dict(c.execute(text("SELECT name,setting FROM pg_settings WHERE name IN ('max_connections','shared_buffers','work_mem','statement_timeout','lock_timeout')")).all()))
        else:r=[dict(v) for v in c.execute(text("SELECT o.id,o.device_id,o.key_epoch,o.sequence_number,o.category,o.occurred_at,p.created_at,p.status,p.version FROM security_observations o LEFT JOIN policy_signals p ON p.event_id='security:'||o.id ORDER BY o.occurred_at,o.id LIMIT 100000")).mappings()]
    print(json.dumps(r,default=lambda v:v.isoformat() if hasattr(v,'isoformat') else float(v)));e.dispose()
if __name__=='__main__':main()

"""SQL scaling diagnostics in private disposable schemas, never the source lab journal."""
import argparse,json,uuid,hashlib
from pathlib import Path
from sqlalchemy import create_engine,text
from src.runtime import database_url


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();e=create_engine(database_url());results=[]
    for size in [1000,10000,50000,100000]:
        schema='p13plan_'+uuid.uuid4().hex
        with e.begin() as c:
            c.execute(text('CREATE SCHEMA '+schema));c.execute(text('SET LOCAL search_path TO '+schema+',public'))
            c.execute(text('CREATE TABLE source(id text PRIMARY KEY, occurred_at timestamptz NOT NULL)'))
            c.execute(text('CREATE INDEX source_order ON source(occurred_at,id)'))
            c.execute(text('CREATE TABLE consumed(event_id text,version text,PRIMARY KEY(event_id,version))'))
            c.execute(text('CREATE TABLE pending(event_id text PRIMARY KEY,kind text,occurred_at timestamptz NOT NULL)'))
            c.execute(text('CREATE INDEX pending_order ON pending(kind,occurred_at,event_id)'))
            c.execute(text("INSERT INTO source SELECT lpad(i::text,36,'0'), '2026-01-01'::timestamptz+i*interval '1ms' FROM generate_series(1,:n) i"),dict(n=size))
            c.execute(text("INSERT INTO consumed SELECT 'security:'||id,'v1' FROM source ORDER BY occurred_at LIMIT :n"),dict(n=size-32))
            c.execute(text("INSERT INTO pending SELECT 'security:'||id,'security',occurred_at FROM source WHERE NOT EXISTS(SELECT 1 FROM consumed WHERE event_id='security:'||source.id AND version='v1')"))
            c.execute(text('ANALYZE source'));c.execute(text('ANALYZE consumed'));c.execute(text('ANALYZE pending'))
            queries=dict(baseline="SELECT * FROM source WHERE NOT EXISTS(SELECT 1 FROM consumed WHERE version='v1' AND event_id='security:'||source.id) ORDER BY occurred_at,id LIMIT 1 FOR UPDATE SKIP LOCKED",optimized="SELECT * FROM pending WHERE kind='security' ORDER BY occurred_at,event_id LIMIT 32 FOR UPDATE")
            rows={}
            for name,sql in queries.items():rows[name]=dict(sql=sql,plans=[c.scalar(text('EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) '+sql)) for _ in range(3)])
            results.append(dict(history=size,pending=32,queries=rows));c.execute(text('DROP SCHEMA '+schema+' CASCADE'))
    data=json.dumps(dict(experiment='private synthetic SQL-shape diagnostic, not authenticated network evidence',source_sha='649a80ff7f7d66f72f5f483b384754ae594f221e',runs=results,exit_code=0),indent=2)
    if a.output=='-':print(data)
    else:Path(a.output).write_text(data);print('Four history sizes, three plans/query: exit0')
if __name__=='__main__':main()

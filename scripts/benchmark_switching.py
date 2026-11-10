"""Bounded real MQTT/TLS static vs switching measurements, dedicated stage8 lab."""
import argparse,json,subprocess,time
from pathlib import Path

SAMPLE=r'''
import time,json,statistics
from datetime import datetime,timezone
from sqlalchemy import create_engine,select,func
from src.runtime import database_url
from src.outbox import outbox
from src.security_events import journal
from src.mongo_repository import MongoRepository
engine=create_engine(database_url());start=datetime.now(timezone.utc);time.sleep(8);end=datetime.now(timezone.utc)
with engine.connect() as c:
 rows=[dict(r) for r in c.execute(select(outbox).where(outbox.c.device_id=='alpha',outbox.c.created_at>=start,outbox.c.created_at<end).order_by(outbox.c.sequence_number).limit(1000)).mappings()]
 backlog=c.scalar(select(func.count()).select_from(outbox).where(outbox.c.status!='delivered'))
 rejected=c.scalar(select(func.count()).select_from(journal).where(journal.c.category=='rejected',journal.c.occurred_at>=start,journal.c.occurred_at<end))
 replay=c.scalar(select(func.count()).select_from(journal).where(journal.c.category=='replay',journal.c.device_id=='alpha',journal.c.occurred_at>=start,journal.c.occurred_at<end))
assert rows
profiles={r['payload']['crypto_profile'] for r in rows};assert len(profiles)==1
latencies=sorted((r['created_at']-datetime.fromisoformat(r['payload']['measured_at'])).total_seconds()*1000 for r in rows)
repo=MongoRepository('relay');deadline=time.monotonic()+5
identities=[f"alpha:{r['key_epoch']}:{r['sequence_number']}" for r in rows]
while time.monotonic()<deadline and repo.collection.count_documents({'_id':{'$in':identities}})<len(rows):time.sleep(.2)
mongo=repo.collection.count_documents({'_id':{'$in':identities}});repo.close()
def p(q):return latencies[min(len(latencies)-1,int((len(latencies)-1)*q))]
with engine.connect() as c:
 delivered=list(c.execute(select(outbox.c.created_at,outbox.c.delivered_at).where(outbox.c.id.in_([r['id'] for r in rows]))))
relay=[(r.delivered_at-r.created_at).total_seconds()*1000 for r in delivered if r.delivered_at]
print(json.dumps(dict(start=start.isoformat(),end=end.isoformat(),duration_seconds=(end-start).total_seconds(),wire_profile=list(profiles)[0],pg_accepted=len(rows),mongo_stored=mongo,undelivered_committed=len(rows)-mongo,received_messages_per_second=len(rows)/(end-start).total_seconds(),delivery_latency_ms=dict(p50=p(.5),p95=p(.95),p99=p(.99)),pg_to_mongo_mean_ms=statistics.mean(relay) if relay else None,global_outbox_backlog=backlog,global_unattributed_rejected=rejected,device_authenticated_replay=replay)))
'''


def main():
    p=argparse.ArgumentParser();p.add_argument('--env-file',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    v=dict(l.split('=',1) for l in a.env_file.read_text().splitlines() if '=' in l and not l.startswith('#'))
    if not v.get('COMPOSE_PROJECT_NAME','').startswith('lcm-stage8-'):p.error('Stage8 isolated project only')
    if a.output.exists():p.error('Immutable output path already exists')
    base=['docker','compose','--env-file',str(a.env_file),'-f','compose.yaml','-f','compose.control.yaml']
    def run(*args):return subprocess.run(base+list(args),capture_output=True,text=True,check=True,timeout=90).stdout
    def probe(action):
        s=run('run','--rm','--no-deps','--entrypoint','python','tests','-m','scripts.control_system_probe',action)
        return json.loads(s[s.index('{'):])
    def current():return next(d for d in probe('status')['devices'] if d['device_id']=='alpha')['effective_profile']
    def switch(target):
        if current()==target:return None
        action='request-ascon' if target=='ascon-aead128-v1' else 'switch-aes'
        report=probe(action)
        deadline=time.monotonic()+25
        while current()!=target and time.monotonic()<deadline:time.sleep(.2)
        assert current()==target
        return report
    samples=[];transitions=[]
    for repeat in range(3):
        for profile in (['ascon-aead128-v1','aes-128-gcm-v1'] if repeat%2==0 else ['aes-128-gcm-v1','ascon-aead128-v1']):
            result=switch(profile)
            if result:transitions.extend(result['measurements'])
            time.sleep(2) # fixed warmup, no control operation during the sample window
            snapshot=subprocess.run(['docker','stats','--no-stream','--format','{{json .}}',v['COMPOSE_PROJECT_NAME']+'-device-alpha-1',v['COMPOSE_PROJECT_NAME']+'-receiver-1'],capture_output=True,text=True,check=True,timeout=10)
            stat=[json.loads(l) for l in snapshot.stdout.splitlines() if l.strip()]
            data=json.loads(run('run','--rm','--no-deps','--entrypoint','python','tests','-c',SAMPLE))
            assert data['mongo_stored']==data['pg_accepted']
            assert data['wire_profile']==('AES-128-GCM' if profile=='aes-128-gcm-v1' else 'Ascon-AEAD128')
            samples.append(dict(repeat=repeat,profile=profile,docker_cpu_ram_snapshots=stat,**data))
    # Include exact committed timestamps for both directions, not request-only timing.
    final=probe('status')
    history=[t for t in final['transitions'] if t['phase']=='EFFECTIVE_CONFIRMED' and t['device_id']=='alpha']
    wanted={r['transition_id'] for r in transitions}
    history=[t for t in history if t['id'] in wanted]
    report=dict(schema_version=1,project=v['COMPOSE_PROJECT_NAME'],devices=3,interval_seconds=.5,qos=1,tls=True,sample_windows=samples,measured_transition_history=history,
        limitations=['8-second windows at configured rate; not capacity benchmark','CPU/RAM snapshots are not peaks','Same host software agents; not Raspberry Pi','Authentication-only latency unavailable; microbenchmark reports authenticated decrypt','No inference/model training; no claim of all publisher loss from PG/Mongo parity'])
    a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':main()

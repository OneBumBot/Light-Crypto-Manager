"""Bounded final faults and stop/resume. Reuse existing PG read-only probes."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime, timezone
from scripts.stage16_demo import Demo, docker_git_sha
from scripts.stage16_smoke import login, wait, switch


def probe(d,action='snapshot',**kwargs):
    value=d.run('run','--rm','-T','--no-deps','--entrypoint','python','tests','-m','scripts.performance_probe',action,input_data=json.dumps(kwargs) if kwargs else None)
    return json.loads(value.stdout[value.stdout.index('{'):])


def brief(value):
    result={k:v for k,v in value.items() if k not in ['identities','mongo_identities']}
    for field in ['identities','mongo_identities']:
        if field in value:
            result[field+'_count']=len(value[field]);result[field+'_sha256']=hashlib.sha256(json.dumps(value[field],sort_keys=True).encode()).hexdigest()
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,default=Path('.local-runtime/stage16/demo'));p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():p.error('Immutable report exists')
    d=Demo(a.directory);s,url,h=login(d,'admin');events=[]
    try:
        for service,hold in [('receiver',2),('mongo',5),('postgres',4),('device-alpha',2),('policy-worker',32)]:
            before=probe(d);start=time.monotonic();print('Fault',service,flush=True);during=None
            try:
                d.run('stop',service);time.sleep(hold)
                if service=='postgres':
                    response=s.get(url+'/api/monitoring',timeout=10);assert response.status_code==503;during=dict(http_status=503,old_snapshot_not_returned=True)
                else:
                    during=probe(d)
                    if service in ['mongo','device-alpha','policy-worker']:assert during['counters'].get('accepted',0)>before['counters'].get('accepted',0)
                    if service=='mongo':assert sum(v for k,v in during['outbox'].items() if k!='delivered')>0
                    if service=='policy-worker':
                        diagnostic=s.get(url+'/api/policy/metrics',timeout=10).json();assert diagnostic['worker_status']!='ready';during['diagnostics']=diagnostic
                    assert during['completed']==before['completed']
            finally:d.run('up','-d','--no-deps','--wait','--wait-timeout','90',service,timeout=150)
            restored=datetime.now(timezone.utc).isoformat();recover=time.monotonic()
            def ready():
                state=probe(d)
                return state if state['counters'].get('accepted',0)>before['counters'].get('accepted',0) and probe(d,'watermark',before=restored)['pending_before_watermark']==0 else None
            after=wait(ready,60)
            assert after['completed']==before['completed']
            if service=='device-alpha':assert next(v for v in after['devices'] if v['device_id']=='alpha')['sequence_reserved']>next(v for v in before['devices'] if v['device_id']=='alpha')['sequence_reserved']
            events.append(dict(service=service,hold_seconds=hold,before=before,during=during,after=after,total_seconds=time.monotonic()-start,post_start_observation_seconds=time.monotonic()-recover,scope='Sampled observation after container start and pre-restore Outbox watermark drain, not universal RTO'))
            a.output.with_suffix('.progress.json').write_text(json.dumps(events,indent=2))
        # Stop controller before durable HTTP request; no fake effective while unavailable.
        before=d.detailed();start=time.monotonic();d.run('stop','control-worker')
        try:
            response=s.post(url+'/api/control/alpha/switch',json=dict(profile='aes-128-gcm-v1',ttl=120),headers=h,timeout=8);assert response.status_code==202;tid=response.json()['transition_id'];time.sleep(2)
            pending=d.detailed();row=next(r for r in pending['transition_evidence'] if r['id']==tid)
            assert row['phase']!='EFFECTIVE_CONFIRMED' and row['receipt'] is None
            assert pending['completed']==before['completed'] and pending['authenticated_ack']==before['authenticated_ack']
        finally:d.run('up','-d','--no-deps','--wait','control-worker')
        recover=time.monotonic()
        done=wait(lambda:next((r for r in s.get(url+'/api/control',timeout=8).json()['transitions'] if r['id']==tid and r['phase']=='EFFECTIVE_CONFIRMED'),None),45)
        actual=d.detailed();assert next(r for r in actual['transition_evidence'] if r['id']==tid)['receipt_matches_committed_admission']
        events.append(dict(service='control-worker',pending=brief(pending),after=brief(actual),transition_id=tid,no_false_effective=True,total_seconds=time.monotonic()-start,post_start_observation_seconds=time.monotonic()-recover))
        switch(d,s,url,h,'ascon-aead128-v1')
        before=d.detailed();keys=json.loads((d.root/'material.json').read_text());d.stop();stopped=d.sqlite_snapshot()
        # Reversible metadata fixtures only; no volume/SQLite/key is removed.
        marker=d.root/'used-volumes.json';saved=marker.read_bytes();negative=[]
        try:
            marker.rename(d.root/'used-volumes.fixture-backup')
            result=subprocess.run([sys.executable,'-m','scripts.stage16_demo','resume','--directory',str(d.root)],capture_output=True,text=True,timeout=45)
            assert result.returncode==2 and 'marker missing' in result.stderr;negative.append(dict(case='missing_used_marker',exit_code=2,refused_before_start=True))
        finally:
            (d.root/'used-volumes.fixture-backup').rename(marker)
        try:
            fake=json.loads(saved);fake[d.project+'_deliberately-missing-fixture']=dict(created_at='not-created');marker.write_text(json.dumps(fake))
            result=subprocess.run([sys.executable,'-m','scripts.stage16_demo','resume','--directory',str(d.root)],capture_output=True,text=True,timeout=45)
            assert result.returncode==2 and 'Used volume missing' in result.stderr;negative.append(dict(case='missing_volume_reference_fixture',exit_code=2,actual_volumes_untouched=True))
        finally:marker.write_bytes(saved)
        assert marker.read_bytes()==saved
        started=time.monotonic();d.start(resume=True);after=d.detailed();sql=d.sqlite_snapshot()
        assert json.loads((d.root/'material.json').read_text())==keys
        assert {r['event_id'] for r in before['identities']}<={r['event_id'] for r in after['identities']}
        assert {r['_id'] for r in before['mongo_identities']}<={r['_id'] for r in after['mongo_identities']}
        assert before['transitions']==after['transitions'] and before['effective_receipts']==after['effective_receipts']
        for device in ['alpha','beta','gamma']:
            assert sql[device]['nonce_reserved_high']>stopped[device]['nonce_reserved_high']
            assert sql[device]['seq']==stopped[device]['seq'] and sql[device]['ledger_count']==stopped[device]['ledger_count']
            assert sql[device]['profile']==stopped[device]['profile']
            assert after['telemetry'][device]['max_sequence']>before['telemetry'][device]['max_sequence']
        report=dict(project=d.project,source_sha=docker_git_sha(),faults=events,stop_resume=dict(before=brief(before),after=brief(after),sqlite_before=stopped,sqlite_after=sql,private_material_unchanged=True,all_prior_pg_mongo_identities_retained=True,new_nonce_ranges=True,observed_resume_seconds=time.monotonic()-started),missing_state_negatives=negative,shadow_failure='NOT_EXECUTED_OPTIONAL_RESEARCH_DEMO_UNAVAILABLE',commands=d.commands,exit_code=0)
        a.output.write_text(json.dumps(report,indent=2));print('Actual recovery and stop/resume assertions passed; exit0')
    finally:s.close()

if __name__=='__main__':main()

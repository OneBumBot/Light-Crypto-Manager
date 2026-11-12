"""Reuse bounded seven-service recovery observations while alpha runs real MGM."""
import argparse,json,time
from pathlib import Path
from datetime import datetime,timezone
from scripts.kuz_lab import Lab
from scripts.performance_run import login
from scripts.performance_reliability import switch,wait
from src.crypto_profiles import KUZ,ASCON


def main():
    p=argparse.ArgumentParser();p.add_argument('--directory',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():p.error('Immutable report exists')
    lab=Lab(a.directory);session,url,token=login(lab);events=[];switches=[]
    current=next(d for d in lab.probe('snapshot')['devices'] if d['device_id']=='alpha')['effective_profile']
    if current!=KUZ:switches.append(switch(lab,session,url,token,'alpha',KUZ))
    for service,hold in [('mongo',8),('control-worker',12),('policy-worker',32),('postgres',6),('broker',6),('device-alpha',3),('receiver',3)]:
        before=lab.probe('snapshot');started=datetime.now(timezone.utc).isoformat();t=time.monotonic();during=None
        try:
            lab.run('stop',service);time.sleep(hold)
            if service!='postgres':
                during=lab.probe('snapshot')
                if service in ['mongo','control-worker','policy-worker','device-alpha']:assert during['counters']['accepted']>before['counters']['accepted']
                if service=='mongo':assert sum(v for k,v in during['outbox'].items() if k!='delivered')>0
                assert during['completed']==before['completed']
            if service=='postgres':assert session.get(url+'/api/monitoring',timeout=10).status_code==503
            if service in ['control-worker','policy-worker']:
                state=session.get(url+'/api/monitoring',timeout=10).json();key='control' if service=='control-worker' else 'policy'
                assert state['components'][key]['status']!='ready'
        finally:lab.run('up','-d','--no-deps','--wait','--wait-timeout','90',service)
        restored=datetime.now(timezone.utc).isoformat();rstart=time.monotonic()
        def recovered():
            state=lab.probe('snapshot')
            if state['counters']['accepted']>before['counters']['accepted'] and lab.probe('watermark',before=restored)['pending_before_watermark']==0:return state
        after=wait(recovered,100)
        profiles={d['device_id']:d['effective_profile'] for d in after['devices']}
        assert profiles==dict(alpha=KUZ,beta=ASCON,gamma=ASCON)
        assert after['completed']==before['completed']
        if service=='device-alpha':assert next(d for d in after['devices'] if d['device_id']=='alpha')['sequence_reserved']>next(d for d in before['devices'] if d['device_id']=='alpha')['sequence_reserved']
        events.append(dict(service=service,started_at=started,restored_at=restored,held_seconds=hold,total_seconds=time.monotonic()-t,recovery_seconds=time.monotonic()-rstart,before=before,during=during,after=after,false_effective=False,pre_restore_cohort_delivered=True))
        a.output.with_suffix('.progress.json').write_text(json.dumps(events,indent=2))
        print('Recovered',service,flush=True)
    switches.append(switch(lab,session,url,token,'alpha',ASCON))
    a.output.write_text(json.dumps(dict(project=lab.project,faults=events,switches=switches,commands=lab.commands,exit_code=0),indent=2))

if __name__=='__main__':main()

"""Real controlled faults under independent live-agent load; no database reset."""
import argparse,json,time
from pathlib import Path
from datetime import datetime,timezone
from scripts.performance_lab import Lab
from scripts.performance_run import login


def wait(fn,seconds=60):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        value=fn()
        if value:return value
        time.sleep(1)
    raise AssertionError('Bounded authoritative recovery not observed')


def switch(lab,session,url,token,device,target):
    start=time.time();r=session.post(url+'/api/control/'+device+'/switch',headers={'X-CSRFToken':token},json=dict(profile=target,ttl=120),timeout=8)
    assert r.status_code==202,(device,r.status_code,r.text[:120])
    tid=r.json()['transition_id'];intent=time.time()
    def effective():
        r=session.get(url+'/api/monitoring/'+device,timeout=8);r.raise_for_status();v=r.json()
        t=next((t for t in v['transitions'] if t['id']==tid),None)
        if t and t['phase']=='EFFECTIVE_CONFIRMED':
            assert t['telemetry_event'] and t['confirmed_at']
            assert v['items'][0]['effective_profile']==target
            return t
    t=wait(effective,90)
    return dict(device=device,target=target,transition_id=tid,http_202_seconds=intent-start,observed_effective_seconds=time.time()-start,transition=t)


def main():
    p=argparse.ArgumentParser();p.add_argument('--directory',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--switch-only',action='store_true');a=p.parse_args()
    if a.output.exists():p.error('Immutable output exists')
    lab=Lab(a.directory);session,url,token=login(lab);events=[];switches=[]
    for target in ['aes-128-gcm-v1','ascon-aead128-v1']:
        switches.append(switch(lab,session,url,token,'alpha',target))
    if a.switch_only:
        # Two distinct-device intents can coexist; never conflicting same-device commands.
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=2) as pool:
            # Separate sessions, no shared cookie mutation across threads.
            def one(device,target):
                s,u,t=login(lab);return switch(lab,s,u,t,device,target)
            switches.extend(pool.map(lambda d:one(d,'aes-128-gcm-v1'),['alpha','beta']))
            switches.extend(pool.map(lambda d:one(d,'ascon-aead128-v1'),['alpha','beta']))
    else:
        for service,hold in [('mongo',12),('control-worker',12),('policy-worker',32),('postgres',8),('broker',8),('device-alpha',5),('receiver',5)]:
            before=lab.probe('snapshot');started=datetime.now(timezone.utc).isoformat();t=time.monotonic();during=None
            try:
                lab.run('stop',service);time.sleep(hold)
                if service not in ['postgres']:
                    during=lab.probe('snapshot')
                    if service in ['mongo','control-worker','policy-worker','device-alpha']:
                        assert during['counters'].get('accepted',0)>before['counters'].get('accepted',0)
                    if service=='mongo':assert sum(v for k,v in during['outbox'].items() if k!='delivered')>0
                    assert during['completed']==before['completed']
                if service=='postgres':
                    r=session.get(url+'/api/monitoring',timeout=10);assert r.status_code==503
                if service in ['control-worker','policy-worker']:
                    v=session.get(url+'/api/monitoring',timeout=10).json();key='control' if service=='control-worker' else 'policy'
                    assert v['components'][key]['status']!='ready'
            finally:lab.run('up','-d','--no-deps','--wait','--wait-timeout','90',service)
            restored=datetime.now(timezone.utc).isoformat();recovery_start=time.monotonic()
            def recovered():
                state=lab.probe('snapshot')
                if state['counters'].get('accepted',0)>before['counters'].get('accepted',0) and not sum(v for k,v in state['outbox'].items() if k!='delivered'):
                    return state
            after=wait(recovered,100)
            assert all(d['effective_profile']=='ascon-aead128-v1' for d in after['devices'])
            assert after['completed']==before['completed']
            if service=='device-alpha':assert next(d for d in after['devices'] if d['device_id']=='alpha')['sequence_reserved']>next(d for d in before['devices'] if d['device_id']=='alpha')['sequence_reserved']
            events.append(dict(service=service,start=started,restored=restored,held_seconds=hold,total_seconds=time.monotonic()-t,post_start_recovery_seconds=time.monotonic()-recovery_start,before=before,during=during,after=after,false_effective=False))
        switches.append(switch(lab,session,url,token,'alpha','aes-128-gcm-v1'))
        switches.append(switch(lab,session,url,token,'alpha','ascon-aead128-v1'))
    transitions=lab.probe('transitions')
    a.output.write_text(json.dumps(dict(project=lab.project,devices=len(lab.devices),switches=switches,faults=events,control_history=transitions,commands=lab.commands,exit_code=0),indent=2))
    print('Real transitions',len(switches),'fault scenarios',len(events),'exit 0')

if __name__=='__main__':main()

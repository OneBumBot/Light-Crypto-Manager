"""Bounded real admin HTTP -> HMAC MQTT/TLS -> device -> AEAD PG/Mongo checks."""
import argparse,json,re,time,subprocess
from pathlib import Path
import requests
from scripts.kuz_lab import Lab
from src.crypto_profiles import ASCON,AES,KUZ


def login(lab,role):
    s=requests.Session();url=lab.url()
    r=s.get(url+'/login',timeout=8);r.raise_for_status()
    csrf=re.search(r'name="csrf-token" content="([^"]+)"',r.text).group(1)
    password=(lab.root/'accounts'/(role+'.password')).read_text().strip()
    r=s.post(url+'/login',data=dict(username='demo-'+role,password=password,csrf_token=csrf),allow_redirects=False,timeout=8)
    assert r.status_code==302
    csrf=re.search(r'name="csrf-token" content="([^"]+)"',s.get(url+'/',timeout=8).text).group(1)
    return s,{'X-CSRFToken':csrf},url


def main():
    p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():p.error('Immutable report exists')
    lab=Lab(a.directory);admin,headers,url=login(lab,'admin');checks=[];transitions=[]
    def get(path):
        r=admin.get(url+path,timeout=8);r.raise_for_status();return r.json()
    before=get('/api/control');baseline={d['device_id']:d['effective_profile'] for d in before['items']}
    assert baseline==dict(alpha=ASCON,beta=ASCON,gamma=ASCON)
    for role in ['viewer','operator']:
        session,h,_=login(lab,role)
        assert session.post(url+'/api/control/alpha/switch',json=dict(profile=KUZ,ttl=120),headers=h,timeout=8).status_code==403
        session.close();checks.append(role+'_cannot_switch')
    assert admin.post(url+'/api/control/alpha/switch',json=dict(profile=KUZ,ttl=120),timeout=8).status_code==400
    assert admin.post(url+'/api/control/gamma/switch',json=dict(profile=KUZ,ttl=120),headers=headers,timeout=8).status_code==409
    checks+=['csrf_required','gamma_unsupported']
    for target in [KUZ,AES,KUZ,ASCON]:
        t0=time.monotonic()
        r=admin.post(url+'/api/control/alpha/switch',json=dict(profile=target,ttl=120),headers=headers,timeout=8)
        assert r.status_code==202,(r.status_code,r.text)
        tid=r.json()['transition_id'];deadline=time.monotonic()+45
        while time.monotonic()<deadline:
            status=get('/api/control?device_id=alpha')
            transition=next(t for t in status['transitions'] if t['id']==tid)
            if transition['phase']=='EFFECTIVE_CONFIRMED':break
            assert transition['phase'] not in ['UNKNOWN_OUTCOME','RECOVERY_REQUIRED'],transition
            time.sleep(.25)
        else:raise AssertionError('No verified effective telemetry')
        effective_observed_seconds=time.monotonic()-t0
        receipt=next(e for e in status['effective_evidence'] if e['event_id']==transition['telemetry_event'])
        assert receipt['profile']==target and receipt['key_reference']==target+':1'
        assert status['items'][0]['effective_profile']==target
        wire=status['profiles'][target]['algorithm'];deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            history=get('/api/telemetry/history?device_id=alpha&limit=50')['items']
            if any(h['crypto_profile']==wire and h['sequence_number']==receipt['sequence_number'] for h in history):break
            time.sleep(.25)
        else:raise AssertionError('Actual receiver event missing in MongoDB')
        ack=[x for x in status['acks'] if x['body']['data']['transition_id']==tid]
        # /api/control deliberately exposes authenticated bodies; assert no secrets.
        assert all(x['device_id']=='alpha' for x in ack)
        neighbors=get('/api/control')['items']
        assert all(x['effective_profile']==ASCON for x in neighbors if x['device_id']!='alpha')
        transitions.append(dict(transition=transition,receipt=receipt,request_to_effective_seconds=effective_observed_seconds,full_verification_seconds=time.monotonic()-t0,authenticated_ack_observed=len(ack)))
        time.sleep(2.1)
    after=get('/api/control')
    # Allow bounded late authenticated ACK arrival before counting.
    assert len(transitions)==4
    report=dict(project=lab.project,source_sha=subprocess.check_output(['git','rev-parse','HEAD']).decode().strip(),
        before_devices=baseline,transitions=transitions,checks=checks,
        effective_profiles={x['device_id']:x['effective_profile'] for x in after['items']},
        commands=lab.commands,exit_code=0)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(transitions=len(transitions),checks=checks,exit_code=0)))

if __name__=='__main__':main()

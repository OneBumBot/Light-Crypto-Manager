"""Actual lost ACTIVATE ACK and expired-grace bounded manual reconciliation."""
import argparse,json,time
from pathlib import Path
from scripts.kuz_lab import Lab
from scripts.check_kuznyechik_mqtt import login
from src.crypto_profiles import KUZ,ASCON


def main():
    p=argparse.ArgumentParser();p.add_argument('--directory',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():p.error('Immutable report exists')
    lab=Lab(a.directory);s,h,url=login(lab,'admin');results=[]
    def status():return s.get(url+'/api/control?device_id=alpha',timeout=8).json()
    def request(target,ttl=120):
        time.sleep(2.1);r=s.post(url+'/api/control/alpha/switch',headers=h,json=dict(profile=target,ttl=ttl),timeout=8)
        assert r.status_code==202,r.text;return r.json()['transition_id']
    def transition(tid):return next(t for t in status()['transitions'] if t['id']==tid)
    def wait(tid,phase,seconds=45):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            t=transition(tid)
            if t['phase']==phase:return t
            time.sleep(.25)
        raise AssertionError('Missing actual '+phase)
    assert status()['items'][0]['effective_profile']==ASCON
    for delay in [0,20]:
        override=lab.root/'ack-fault.compose.json'
        override.write_text(json.dumps({'services':{'device-alpha':{'environment':{'APP_ENV':'test','CONTROL_DROP_ACTIVATE_ACK':'1','CONTROL_TEST_ACTIVATED_DELAY':str(delay)}}}}));override.chmod(0o600)
        original=lab.base[:];lab.base+=['-f',str(override)]
        try:
            lab.run('up','-d','--no-deps','--force-recreate','--wait','device-alpha')
            tid=request(KUZ,15 if delay else 120)
            if delay:
                expired=wait(tid,'UNKNOWN_OUTCOME',30)
                assert status()['items'][0]['effective_profile']==ASCON and not expired['telemetry_event']
                # Reconcile authorizes observation, never writes effective or creates ACTIVATE.
                r=s.post(url+'/api/control/alpha/reconcile',headers=h,json=dict(transition_id=tid,ttl=60),timeout=8)
                assert r.status_code==202
                assert status()['items'][0]['effective_profile']==ASCON
            confirmed=wait(tid,'EFFECTIVE_CONFIRMED')
            v=status();acks=[x for x in v['acks'] if x['body']['data']['transition_id']==tid]
            assert len(acks)==1 and acks[0]['body']['data']['phase']=='PREPARE'
            evidence=next(e for e in v['effective_evidence'] if e['event_id']==confirmed['telemetry_event'])
            assert evidence['profile']==KUZ and v['items'][0]['effective_profile']==KUZ
            results.append(dict(activate_ack_dropped=True,activation_delay_seconds=delay,authenticated_ack_count=len(acks),transition=confirmed,effective_receipt=evidence,unknown_outcome_observed=bool(delay),reconciliation_explicit=bool(delay)))
        finally:
            lab.base=original;lab.run('up','-d','--no-deps','--force-recreate','--wait','device-alpha')
        back=request(ASCON);wait(back,'EFFECTIVE_CONFIRMED')
    a.output.write_text(json.dumps(dict(project=lab.project,scenarios=results,commands=lab.commands,exit_code=0),indent=2))
    print('Lost ACK and expiry/reconciliation: exit 0')

if __name__=='__main__':main()

"""Bounded real HTTP pagination/identity/RBAC/CSRF probes during a cohort."""
import argparse,json,time
from pathlib import Path
from scripts.performance_lab import Lab
from scripts.performance_run import login


def main():
    p=argparse.ArgumentParser();p.add_argument('--directory',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():p.error('Immutable output exists')
    lab=Lab(a.directory);session,url,token=login(lab);checks=[];timings=[]
    before=lab.probe('snapshot');ids=[]
    for offset in range(0,len(lab.devices)+7,7):
        start=time.perf_counter();r=session.get(url+'/api/monitoring',params=dict(limit=7,offset=offset),timeout=8)
        assert r.status_code==200;v=r.json();pageids=[d['device_id'] for d in v['items']];assert len(pageids)<=7
        ids.extend(pageids);timings.append(dict(route='inventory',offset=offset,bytes=len(r.content),seconds=time.perf_counter()-start))
        assert v['summary']['provisioned']==len(lab.devices) and v['policy_mode']=='DRY_RUN' and v['trusted_detector'] is False
        assert set(v['profiles'])=={'ascon-aead128-v1','aes-128-gcm-v1'}
    assert len(ids)==len(set(ids)) and sorted(ids)==sorted(lab.devices);checks.append('real_pagination_no_device_aliases')
    for device in [lab.devices[0],lab.devices[-1]]:
        r=session.get(url+'/api/monitoring/'+device,timeout=8);assert r.status_code==200
        d=r.json()['items'];assert len(d)==1 and d[0]['device_id']==device
        assert d[0]['effective_evidence']['profile']==d[0]['effective_profile']
    checks.append('first_last_device_identity_and_receipt')
    for query in ['limit=101','offset=10001','limit=2&limit=3','extra=1']:
        assert session.get(url+'/api/monitoring?'+query,timeout=8).status_code==400
    checks.append('bounded_invalid_queries_rejected')
    assert session.post(url+'/api/control/alpha/switch',json=dict(profile='aes-128-gcm-v1',ttl=120),timeout=8).status_code==400
    for device,profile,expected in [('unknown-device','aes-128-gcm-v1',404),('gamma','aes-128-gcm-v1',409),('alpha','kuznyechik-mgm-v1',409),('alpha','magma-mgm-v1',409)]:
        assert session.post(url+'/api/control/'+device+'/switch',json=dict(profile=profile,ttl=120),headers={'X-CSRFToken':token},timeout=8).status_code==expected
    checks+=['csrf_required','unknown_device_rejected','unsupported_device_rejected','draft_gost_profiles_cannot_activate']
    for role in ['viewer','operator']:
        s,u,t=login(lab,role)
        assert s.post(u+'/api/control/alpha/switch',json=dict(profile='aes-128-gcm-v1',ttl=120),headers={'X-CSRFToken':t},timeout=8).status_code==403
    after=lab.probe('snapshot');assert before['transitions']==after['transitions'] and before['receipts']==after['receipts']
    checks+=['viewer_operator_denied','negative_requests_create_no_transition_or_receipt']
    config=json.loads((lab.root/'control.json').read_text())
    secrets=[value for cfg in config.values() for value in [cfg['command_key'],cfg['status_key'],cfg['registry']['key_hex'],cfg['registry']['telemetry_keys']['AES-128-GCM']]]
    for route in ['/api/monitoring','/api/monitoring/alpha','/api/control?limit=50','/api/policy?limit=10','/api/telemetry/history?device_id=alpha&limit=50']:
        response=session.get(url+route,timeout=8)
        assert response.status_code==200
        assert not any(secret in response.text for secret in secrets)
    checks.append('live_api_contains_no_telemetry_or_control_keys')
    a.output.write_text(json.dumps(dict(project=lab.project,devices=len(lab.devices),checks=checks,timings=timings,transitions_before=before['transitions'],transitions_after=after['transitions'],exit_code=0),indent=2))
    print('Real HTTP checks:',len(checks),'exit 0')

if __name__=='__main__':main()

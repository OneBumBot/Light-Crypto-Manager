"""End-to-end stage9 orchestration. Requires its dedicated lab; never deletes volumes."""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
import requests
from scripts.stage9_common import Demo


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--browser',action='store_true');a=p.parse_args()
    if a.output.exists():p.error('Immutable report exists')
    d=Demo(a.directory);url=d.url();before=d.probe('ready');checks=[]
    def session(role):
        s=requests.Session();r=s.get(url+'/login',timeout=8);r.raise_for_status()
        csrf=re.search(r'name="csrf-token" content="([^"]+)"',r.text).group(1)
        password=(d.root/'accounts'/(role+'.password')).read_text().strip()
        r=s.post(url+'/login',data=dict(username='demo-'+role,password=password,csrf_token=csrf),allow_redirects=False,timeout=8)
        assert r.status_code==302
        token=re.search(r'name="csrf-token" content="([^"]+)"',s.get(url+'/',timeout=8).text).group(1)
        return s,{'X-CSRFToken':token}
    admin,headers=session('admin')
    for role in ['viewer','operator']:
        s,h=session(role)
        assert s.get(url+'/api/monitoring',timeout=8).status_code==200
        assert s.post(url+'/api/control/alpha/switch',json=dict(profile='aes-128-gcm-v1',ttl=120),headers=h,timeout=8).status_code==403
        s.close();checks.append(role+'_cannot_switch')
    body=dict(profile='aes-128-gcm-v1',ttl=120)
    assert admin.post(url+'/api/control/alpha/switch',json=body,timeout=8).status_code==400
    assert admin.post(url+'/api/control/unknown/switch',json=body,headers=headers,timeout=8).status_code==404
    assert admin.post(url+'/api/control/gamma/switch',json=body,headers=headers,timeout=8).status_code==409
    assert admin.post(url+'/api/control/alpha/switch',json=dict(profile='unknown',ttl=120),headers=headers,timeout=8).status_code==409
    checks+=['csrf_required','unknown_device_rejected','gamma_unsupported_rejected','unknown_profile_rejected']
    snapshot=admin.get(url+'/api/monitoring',timeout=8).json()
    assert len(snapshot['items'])==3 and snapshot['summary']['recent']==3
    assert snapshot['components']['receiver']['status']=='ready' and snapshot['components']['postgres']['status']=='available'
    assert snapshot['components']['mongo']['status']=='available'
    assert snapshot['policy_mode']=='DRY_RUN' and snapshot['trusted_detector'] is False
    assert snapshot['components']['ml']['status']=='disabled'
    for item in snapshot['items']:
        identity=item['device_id'];assert item['effective_evidence']['event_id'] and item['telemetry']['device_id']==identity
        history=admin.get(url+'/api/telemetry/history',params=dict(device_id=identity,limit=5),timeout=8).json()['items']
        assert history and all(r['device_id']==identity for r in history)
    raw=json.dumps(snapshot)
    for forbidden in ['key_hex','command_key','status_key','key_fingerprint','sequence_reserved','password','"wire"','"body"']:assert forbidden not in raw
    checks+=['three_real_fresh_aead_devices','mongo_history_identity','no_secrets_in_adapter','ml_absent_not_normal','policy_dry_run']
    # No administrative switch above succeeded. Policy records cannot secretly create commands.
    after_negatives=d.probe('status');assert after_negatives['transitions']==before['transitions']
    checks.append('no_automatic_policy_commands')
    ids=subprocess.check_output(['docker','ps','-q','--filter','label=com.docker.compose.project='+d.project]).decode().split()
    containers=json.loads(subprocess.check_output(['docker','inspect',*ids]));infrastructure=[]
    for c in containers:
        service=c['Config']['Labels']['com.docker.compose.service'];host=c['HostConfig']
        assert all(n.startswith(d.project+'_') for n in c['NetworkSettings']['Networks'])
        assert host['Memory']>0 and host['NanoCpus']>0
        for mount in c['Mounts']:
            if mount['Type']=='volume' and mount.get('Name','').startswith('lcm-'):assert mount['Name'].startswith(d.project+'_')
        infrastructure.append(dict(service=service,image=c['Config']['Image'],image_id=c['Image'],memory=host['Memory'],nano_cpus=host['NanoCpus'],restart_count=c['RestartCount']))
    publishers=[c for c in infrastructure if c['service'].startswith('device-')];assert len(publishers)==3
    checks+=['isolated_network_volumes','cpu_ram_limits','three_active_agent_processes']
    browser_report=None
    if a.browser:
        browser_path=a.output.with_name(a.output.stem+'-browser.json')
        env=dict(os.environ,UV_CACHE_DIR='.cache/uv',PLAYWRIGHT_BROWSERS_PATH='.local-runtime/browsers')
        command=['uv','run','--no-project','--python',sys.executable,'--with','playwright==1.56.0','python','-m','scripts.check_stage9_browser','--directory',str(d.root),'--output',str(browser_path)]
        r=subprocess.run(command,env=env,capture_output=True,text=True,timeout=500)
        a.output.with_suffix('.browser.txt').write_text(r.stdout+r.stderr)
        if r.returncode:raise RuntimeError('Browser E2E failed; see '+str(a.output.with_suffix('.browser.txt')))
        browser_report=json.loads(browser_path.read_text());checks.append('real_browser_e2e')
        # Existing stage8 security probe uses actual signed malformed control traffic over TLS.
        r=d.run('run','--rm','--no-deps','--entrypoint','python','tests','-m','scripts.control_security_probe')
        a.output.with_suffix('.control-security.txt').write_text(r.stdout+r.stderr)
        checks.append('real_tls_hmac_acl_forged_ack_negatives')
    after=d.probe('status')
    if a.browser:
        assert after['completed']>=before['completed']+2 and after['authenticated_ack']>=before['authenticated_ack']+4
        assert all(x['effective_profile']=='ascon-aead128-v1' for x in after['devices'])
    # Drain only after quiescence; accepted minus stored during delivery is NOT loss.
    d.run('stop','device-alpha','device-beta','device-gamma')
    try:
        end=time.monotonic()+45
        while time.monotonic()<end:
            drained=d.probe('status')
            if sum(v for k,v in drained['outbox'].items() if k!='delivered')==0 and sum(v['accepted'] for v in drained['telemetry'].values())==drained['mongo_managed']:break
            time.sleep(.3)
        else:raise AssertionError('Durable admitted telemetry did not finish delivery')
    finally:d.run('up','-d','--no-deps','--wait','device-alpha','device-beta','device-gamma')
    report=dict(project=d.project,git_commit=subprocess.check_output(['git','rev-parse','HEAD']).decode().strip(),before=before,after=after,quiescent=drained,
        active_publishers_measured=len(publishers),infrastructure=infrastructure,checks=checks,browser_report=str(browser_path) if a.browser else 'not_measured',commands=d.commands,exit_code=0)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(checks=checks,transitions_delta=after['transitions']-before['transitions'],quiescent=drained,exit_code=0),indent=2))
    admin.close()

if __name__=='__main__':main()

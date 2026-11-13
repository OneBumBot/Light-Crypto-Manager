"""stage16_final_demo_smoke: real HTTP→HMAC/TLS agents→AEAD→PG→Mongo."""
import json
import re
import time
import requests
from scripts.stage16_demo import AGENTS, docker_git_sha


def login(d, role):
    session=requests.Session();url=d.url()
    response=session.get(url+'/login',timeout=8);response.raise_for_status()
    token=re.search(r'name="csrf-token" content="([^"]+)"',response.text).group(1)
    response=session.post(url+'/login',data=dict(username='demo-'+role,password=(d.root/'accounts'/(role+'.password')).read_text().strip(),csrf_token=token),allow_redirects=False,timeout=8)
    assert response.status_code==302
    token=re.search(r'name="csrf-token" content="([^"]+)"',session.get(url+'/',timeout=8).text).group(1)
    return session,url,{'X-CSRFToken':token}


def wait(call,seconds=45):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        value=call()
        if value:return value
        time.sleep(.3)
    raise AssertionError('Real system condition not reached before bounded deadline')


def switch(d, session, url, headers, target):
    started=time.monotonic()
    response=session.post(url+'/api/control/alpha/switch',json=dict(profile=target,ttl=120),headers=headers,timeout=8)
    assert response.status_code==202,response.status_code
    identity=response.json()['transition_id']
    def completed():
        value=session.get(url+'/api/control',timeout=8).json()
        return next((r for r in value['transitions'] if r['id']==identity and r['phase']=='EFFECTIVE_CONFIRMED'),None)
    transition=wait(completed)
    snapshot=d.detailed()
    proof=next(r for r in snapshot['transition_evidence'] if r['id']==identity)
    acks=[r for r in snapshot['verified_acks'] if r['transition_id']==identity]
    assert {(r['phase'],r['result']) for r in acks}=={('PREPARE','READY'),('ACTIVATE','DEVICE_APPLIED')}
    assert all(r['hmac_digest_matches'] and r['command_digest_matches'] for r in acks)
    assert proof['receipt_matches_committed_admission'] and proof['receipt']['event_id']==transition['telemetry_event']
    assert {r['phase'] for r in snapshot['command_phases'] if r['transition_id']==identity}=={'PREPARE','ACTIVATE'}
    return dict(transition=proof,authenticated_acks=acks,http_to_effective_seconds=time.monotonic()-started)


def stage16_final_demo_smoke(d):
    before=d.detailed();checks=[]
    assert len(before['devices'])==3 and all(d['effective_event'] for d in before['devices'])
    assert before['policy_modes']==['DRY_RUN'] and before['policy_applied']==0
    old={r['device_id']:r for r in before['devices']}
    admin,url,headers=login(d,'admin')
    try:
        for role in ['viewer','operator']:
            session,_,h=login(d,role)
            try:
                assert session.get(url+'/api/monitoring',timeout=8).status_code==200
                assert session.post(url+'/api/control/alpha/switch',json=dict(profile='aes-128-gcm-v1',ttl=120),headers=h,timeout=8).status_code==403
            finally:session.close()
        body=dict(profile='aes-128-gcm-v1',ttl=120)
        assert admin.post(url+'/api/control/alpha/switch',json=body,timeout=8).status_code==400
        assert admin.post(url+'/api/control/gamma/switch',json=body,headers=headers,timeout=8).status_code==409
        checks+=['viewer_operator_denied','csrf_required','gamma_unsupported_rejected']
        monitoring=admin.get(url+'/api/monitoring',timeout=8).json()
        assert monitoring['policy_mode']=='DRY_RUN' and monitoring['trusted_detector'] is False
        assert monitoring['components']['receiver']['status']=='ready'
        assert monitoring['components']['postgres']['status']==monitoring['components']['mongo']['status']=='available'
        assert monitoring['components']['ml']['status']=='disabled'
        assert {r['device_id'] for r in monitoring['items']}=={'alpha','beta','gamma'}
        for device in ['alpha','beta','gamma']:
            assert admin.get(url+'/devices/'+device,timeout=8).status_code==200
            rows=admin.get(url+'/api/telemetry/history',params=dict(device_id=device,limit=3),timeout=8).json()['items']
            assert rows and all(r['device_id']==device for r in rows)
        assert d.detailed()['transitions']==before['transitions'],'Unauthorized or autonomous command'
        checks+=['real_fresh_three_agent_tls_aead_telemetry','mongo_history','policy_dry_run_ml_disabled']
        target='aes-128-gcm-v1' if old['alpha']['effective_profile']=='ascon-aead128-v1' else 'ascon-aead128-v1'
        transitions=[switch(d,admin,url,headers,target),switch(d,admin,url,headers,old['alpha']['effective_profile'])]
        after=d.detailed()
        assert after['completed']==before['completed']+2 and after['transitions']==before['transitions']+2
        assert after['authenticated_ack']==before['authenticated_ack']+4
        for row in after['devices']:
            assert row['effective_profile']==old[row['device_id']]['effective_profile']
            if row['device_id']!='alpha':assert row['command_sequence']==old[row['device_id']]['command_sequence'] and row['effective_event']==old[row['device_id']]['effective_event']
        checks+=['ascon_aes_ascon_http_hmac_switch','ready_activate_ack_independent_verification','effective_matches_new_pg_aead_receipt','beta_gamma_unchanged','no_extra_policy_shadow_command']
        d.run('stop',*AGENTS)
        try:
            quiescent=wait(lambda:(r if not r['pg_identities_missing_in_mongo'] and all(k=='delivered' or v==0 for k,v in r['outbox'].items()) else None) if (r:=d.detailed()) else None)
            assert quiescent['duplicate_identities']==0
            assert len(quiescent['identities'])==len(quiescent['mongo_identities'])
            assert {f"{r['device_id']}:{r['key_epoch']}:{r['sequence_number']}" for r in quiescent['identities']}=={r['_id'] for r in quiescent['mongo_identities']}
            checks+=['outbox_quiescent_drain','exact_pg_mongo_identity_set','nonce_ranges_disjoint','no_duplicate_admissions']
        finally:d.run('up','-d','--no-deps','--wait',*AGENTS)
        return dict(test='stage16_final_demo_smoke',source_sha=docker_git_sha(),project=d.project,before=before,after=after,quiescent=quiescent,transitions=transitions,checks=checks,commands=d.commands,shadow='OPTIONAL_RESEARCH_DEMO_UNAVAILABLE',trusted_detector=False,exit_code=0)
    finally:admin.close()

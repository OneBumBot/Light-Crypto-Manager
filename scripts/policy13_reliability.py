"""Actual Policy faults and browser freshness in a fresh Stage13 crypto lab only."""
import argparse,json,time,subprocess,hashlib
from pathlib import Path
from datetime import datetime,timezone
from scripts.policy13_crypto_lab import Lab
from scripts.policy13_run import probe
from scripts.performance_run import login
from playwright.sync_api import sync_playwright,expect


def wait(fn,seconds=90):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        result=fn()
        if result:return result
        time.sleep(.5)
    raise AssertionError('Bounded recovery condition not reached')


def sql(lab,code):
    program='from sqlalchemy import create_engine,text;from src.runtime import database_url;import json;e=create_engine(database_url());c=e.connect();'+code+';c.close();e.dispose()'
    r=lab.run('run','--rm','-T','--no-deps','--entrypoint','python','tests','-c',program)
    return json.loads(r.stdout)


def durable(lab):
    return sql(lab,"tables=['policy_device_states','policy_signals','policy_decisions','policy_transitions','policy_control_intents','policy_schedule'];print(json.dumps({t:sorted(str(v[0]) for v in c.execute(text('SELECT to_jsonb(t)::text FROM '+t+' t'))) for t in tables}))")


def main():
    p=argparse.ArgumentParser();p.add_argument('--directory',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():p.error('Immutable report')
    lab=Lab(a.directory);s,url,token=login(lab);headers={'X-CSRFToken':token};records=[];base=lab.base[:]
    before=probe(lab);lab.run('stop','policy-worker');started=datetime.now(timezone.utc).isoformat()
    # Actual incoming authenticated events, no synthetic risk/status fixtures.
    deadline=time.monotonic()+92
    while time.monotonic()<deadline:
        snap=probe(lab);records.append(dict(phase='worker_stopped',snapshot=snap))
        if snap['capacity']['overflow']:raise AssertionError('Overflow is not a successful run')
        time.sleep(min(5,max(0,deadline-time.monotonic())))
    held=probe(lab);assert held['security']['total']>before['security']['total']+150
    # Explicit laboratory slow-consumer fault. Never a performance result.
    profile=Path('scripts/policy13_worker_profile.py').resolve();override=lab.root/'slow-policy.compose.json'
    override.write_text(json.dumps({'services':{'policy-worker':{'command':['python','-m','scripts.policy13_worker_profile'],'environment':{'POLICY_BATCH_SIZE':'1','POLICY13_TEST_DELAY_MS':'500'},'volumes':[str(profile)+':/app/scripts/policy13_worker_profile.py:ro']}}}));override.chmod(0o600)
    lab.base=base+['-f',str(override)];lab.run('up','-d','--no-deps','--wait','policy-worker')
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True);ctx=browser.new_context();page=ctx.new_page();page.route('https://cdn.**/*',lambda route:route.abort());errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(url+'/login');page.locator('[name=username]').fill('demo-viewer');page.locator('[name=password]').fill((lab.root/'accounts/viewer.password').read_text().strip());page.locator('form input[type=submit],form button[type=submit]').first.click();page.wait_for_url(url+'/');page.goto(url+'/policy')
        expect(page.locator('#policyWorkerStatus')).to_contain_text('ready',timeout=15000)
        expect(page.locator('#policyEvidenceStatus')).to_contain_text('stale',timeout=15000)
        expect(page.locator('#policyQueueStatus')).to_contain_text('lagging',timeout=15000)
        actual=s.get(url+'/api/policy',timeout=8).json()['diagnostics'];assert actual['worker_status']=='ready' and actual['backlog_status']=='lagging'
        page.screenshot(path=str(a.output.with_suffix('.png')),full_page=True)
        records.append(dict(phase='real_ready_but_lagging',diagnostics=actual,throttle_ms=500,batch_size=1,fault_injection=True))
        # Genuine policy activation during durable backlog; no control command.
        overview=s.get(url+'/api/policy',timeout=8).json();old=next(v for v in overview['versions'] if v['version']==overview['active_version']);rules=dict(old['config']);rules['window_seconds']=59
        r=s.post(url+'/api/policy/versions',headers=headers,json=dict(version='stage13-recovery-v2',rules=rules,activate=True),timeout=10);assert r.status_code==200
        new=s.get(url+'/api/policy',timeout=8).json();active=next(v for v in new['versions'] if v['version']=='stage13-recovery-v2');assert active['sha256']!=old['sha256']
        records.append(dict(phase='version_activation_with_backlog',old_version=old['version'],old_sha=old['sha256'],new_version=active['version'],new_sha=active['sha256'],http_status=r.status_code))
        # Retention while real unread events exist. Young source rows cannot be removed.
        prune="from src.policy.worker import prune_journal;from sqlalchemy import select,func;print(json.dumps({'pruned':prune_journal(c,1,c.scalar(select(func.clock_timestamp())))}));c.commit()"
        result=sql(lab,prune);assert result['pruned']==0;records.append(dict(phase='retention_during_backlog',**result))
        lab.base=base;lab.run('up','-d','--no-deps','--force-recreate','--wait','policy-worker')
        wait(lambda:probe(lab)['security']['pending']==0)
        page.reload();expect(page.locator('#policyEvidenceStatus')).to_contain_text('fresh',timeout=15000)
        assert s.get(url+'/api/policy',timeout=8).json()['live_control_enabled'] is False
        import re
        pattern=re.compile(r'.*/api/policy(?:\?.*)?$')
        real=s.get(url+'/api/policy',timeout=8).json();payload=json.loads(json.dumps(real));attack='<img id="policy13-xss" src=x onerror="window.policy13Injected=1">'
        payload['diagnostics']['active_version']=attack;payload['diagnostics']['worker_status']=attack
        page.route(pattern,lambda route:route.fulfill(status=200,content_type='application/json',body=json.dumps(payload)))
        page.reload();expect(page.locator('#policyWorkerStatus')).to_contain_text(attack,timeout=15000)
        assert page.locator('#policy13-xss').count()==0 and page.evaluate('window.policy13Injected || 0')==0
        page.unroute(pattern);page.route(pattern,lambda route:route.fulfill(status=200,content_type='application/json',body='{}'))
        expect(page.locator('#policyWorkerStatus')).to_contain_text('unknown',timeout=15000)
        expect(page.locator('#policyOverview')).to_have_text('')
        page.unroute(pattern);page.reload();expect(page.locator('#policyEvidenceStatus')).to_contain_text('fresh',timeout=15000)
        records.append(dict(phase='policy_dom_fixtures_separate_from_real_data',html_attribute_injection_no_execution=True,malformed_response_clears_previous_snapshot=True))
        browser.close();assert not errors
    # Actual SIGKILL with DB transaction open, once after claim and once after writes.
    for phase in ['after_claim','before_commit']:
        lab.run('stop','policy-worker');time.sleep(5);before_rows=durable(lab);fault_started=time.monotonic();fault_at=datetime.now(timezone.utc).isoformat()
        ids=sql(lab,"print(json.dumps(list(c.scalars(text('SELECT event_id FROM policy_pending ORDER BY kind,sort_at,event_id LIMIT 32')))))")
        assert ids
        name=lab.project+'-policy-fault';flag='/tmp/policy13-fault.json'
        code="import time,json;from pathlib import Path;from sqlalchemy import create_engine;from src.runtime import database_url;from src.policy.worker import poll_batch;e=create_engine(database_url());def_placeholder"
        code=code.replace('def_placeholder',"\ndef hold():\n Path('"+flag+"').write_text(json.dumps({'phase':'"+phase+"','transaction_open':True}));time.sleep(60)\npoll_batch(e,limit=32,"+phase+"=hold)")
        lab.run('run','--rm','-d','--no-deps','--name',name,'--entrypoint','python','policy-worker','-c',code)
        try:
            def flag_ready():
                r=subprocess.run(['docker','exec',name,'cat',flag],capture_output=True,text=True,timeout=5)
                return json.loads(r.stdout) if r.returncode==0 else None
            observed=wait(flag_ready,20);subprocess.run(['docker','kill','--signal','KILL',name],check=True,capture_output=True,timeout=10)
            wait(lambda:sql(lab,"print(json.dumps({'released':c.scalar(text('SELECT pg_try_advisory_xact_lock(734819207)'))}))")['released'],20)
            wait(lambda:durable(lab)==before_rows,20)
            remaining=sql(lab,"print(json.dumps(list(c.scalars(text('SELECT event_id FROM policy_pending')))))");assert set(ids)<=set(remaining)
            records.append(dict(phase='sigkill_'+phase,started_at=fault_at,transaction_observed=observed,authoritative_rows_unchanged=True,pending_ids_preserved=len(ids),fault_seconds=time.monotonic()-fault_started))
        finally:
            subprocess.run(['docker','rm','-f',name],capture_output=True,timeout=10)
        restored=time.monotonic();lab.run('up','-d','--no-deps','--wait','policy-worker');wait(lambda:probe(lab)['security']['pending']==0)
        records[-1]['recovery_seconds']=time.monotonic()-restored
    # Real PG outage: browser clears current state; same volume resumes durable admission.
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True);page=browser.new_page();page.route('https://cdn.**/*',lambda route:route.abort());page.goto(url+'/login');page.locator('[name=username]').fill('demo-viewer');page.locator('[name=password]').fill((lab.root/'accounts/viewer.password').read_text().strip());page.locator('form input[type=submit],form button[type=submit]').first.click();page.wait_for_url(url+'/');page.goto(url+'/policy')
        expect(page.locator('#policyWorkerStatus')).to_contain_text('ready',timeout=15000)
        prior=probe(lab);outage_at=datetime.now(timezone.utc).isoformat();lab.run('stop','postgres')
        expect(page.locator('#policyWorkerStatus')).to_contain_text('unknown',timeout=25000);expect(page.locator('#policyOverview')).to_have_text('')
        restore=time.monotonic();lab.run('up','-d','--no-deps','--wait','postgres');wait(lambda:probe(lab)['security']['total']>prior['security']['total'] and probe(lab)['security']['pending']==0,90)
        page.reload();expect(page.locator('#policyWorkerStatus')).to_contain_text('ready',timeout=15000)
        records.append(dict(phase='postgres_outage_and_ui_unavailable',started_at=outage_at,recovery_seconds=time.monotonic()-restore,same_volume=True,stale_snapshot_cleared=True))
        browser.close()
    final=probe(lab);assert final['capacity']['overflow']==0
    assert sql(lab,"print(json.dumps({'commands':c.scalar(text('SELECT count(*) FROM live_control_commands')),'duplicate_signals':c.scalar(text('SELECT count(*) FROM(SELECT event_id,version FROM policy_signals GROUP BY event_id,version HAVING count(*)>1)t')),'duplicate_decisions':c.scalar(text('SELECT count(*) FROM(SELECT event_id,version FROM policy_decisions GROUP BY event_id,version HAVING count(*)>1)t'))}))")==dict(commands=0,duplicate_signals=0,duplicate_decisions=0)
    report=dict(project=lab.project,source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),before=before,after=final,events=records,browser_errors=[],policy='DRY_RUN',trusted_detector=False,commands=lab.commands,exit_code=0)
    a.output.write_text(json.dumps(report,indent=2));print('Actual backlog, UI, activation, retention, two SIGKILL recoveries: exit0')
if __name__=='__main__':main()

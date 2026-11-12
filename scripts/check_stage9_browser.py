"""Real Chromium user journey; actual HTTP/HMAC agents/AEAD receipts, no fake success."""
import argparse
import copy
import json
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
from scripts.stage9_common import Demo
from scripts.performance_lab import Lab
from scripts.kuz_lab import Lab as KuzLab
from scripts.crypto_research_lab import Lab as ResearchLab


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():p.error('Immutable output exists')
    d=(ResearchLab(a.directory) if (a.directory/'stage12.json').exists() else KuzLab(a.directory) if (a.directory/'stage11.json').exists() else Lab(a.directory) if (a.directory/'stage10.json').exists() else Demo(a.directory));url=d.url();checks=[]
    def reply(body):
        return lambda route:route.fulfill(content_type='application/json',body=json.dumps(body))
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True)
        ctx=browser.new_context(viewport=dict(width=1366,height=900),timezone_id='Europe/Moscow');page=ctx.new_page();errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        # Demo remains usable without CDN. Test our bundled app assets and safe DOM.
        page.route('https://cdn.**/*',lambda route:route.abort())
        def login(role):
            page.goto(url+'/login');page.locator('[name=username]').fill('demo-'+role)
            page.locator('[name=password]').fill((d.root/'accounts'/(role+'.password')).read_text().strip())
            page.locator('form input[type=submit], form button[type=submit]').first.click();page.wait_for_url(url+'/')
            page.wait_for_selector('#device-rows tr[data-device=alpha]')
        login('viewer');expect(page.locator('#device-rows tr')).to_have_count(len(d.devices) if isinstance(d,Lab) else 3)
        page.locator('a[href="/devices/alpha"]').click();page.wait_for_selector('#effective-profile')
        expect(page.locator('#effective-profile')).to_have_text('Ascon-AEAD128')
        expect(page.locator('#history-rows tr').first).to_be_visible()
        expect(page.locator('#device-policy')).to_contain_text('DRY_RUN')
        assert page.locator('#switch-submit').count()==0
        checks+=['viewer_real_device_card','viewer_mongo_history','viewer_policy_dry_run','viewer_no_switch_control']
        # Same-origin logout still uses protected POST form.
        page.locator('form[action="/logout"] button').click();page.wait_for_url('**/login')
        login('admin');page.goto(url+'/devices/alpha');page.wait_for_selector('#effective-profile')
        def switch(label):
            page.locator('#target-profile').select_option(label=label)
            page.locator('#switch-submit').click();expect(page.locator('#confirm-dialog')).to_be_visible()
            page.locator('#confirm-action').click()
            expect(page.locator('#switch-message')).to_contain_text('Запрос сохранён',timeout=15000)
            expect(page.locator('#effective-profile')).to_have_text(label,timeout=45000)
            expect(page.locator('#transition-history')).to_contain_text('EFFECTIVE_CONFIRMED')
            expect(page.locator('#transition-history')).to_contain_text('Authenticated device ACK')
            expect(page.locator('#transition-history')).to_contain_text('Verified telemetry')
        if isinstance(d,(KuzLab,ResearchLab)):
            switch('Kuznyechik-MGM');checks.append('browser_real_ascon_to_kuznyechik')
        switch('AES-128-GCM');checks.append('browser_real_ascon_or_kuznyechik_to_aes')
        if isinstance(d,(KuzLab,ResearchLab)):
            switch('Kuznyechik-MGM');checks.append('browser_real_aes_to_kuznyechik')
        page.goto(url+'/');page.wait_for_selector('#device-rows tr[data-device=beta]')
        for device in ['beta','gamma']:
            assert page.locator('tr[data-device='+device+'] td').nth(3).inner_text().startswith('Ascon-AEAD128')
        page.goto(url+'/devices/gamma');page.wait_for_selector('#effective-profile')
        assert page.locator('#target-profile option[value="aes-128-gcm-v1"]').count()==0
        expect(page.locator('#switch-submit')).to_be_disabled();checks+=['neighbors_unchanged','gamma_capability_picker']
        page.goto(url+'/devices/alpha');page.wait_for_selector('#effective-profile');switch('Ascon-AEAD128')
        page.reload();expect(page.locator('#effective-profile')).to_have_text('Ascon-AEAD128',timeout=15000)
        checks+=['browser_real_aes_to_ascon','authoritative_after_reload']
        a.output.parent.mkdir(parents=True,exist_ok=True)
        page.screenshot(path=str(a.output.with_suffix('.desktop.png')),full_page=True)
        page.set_viewport_size(dict(width=390,height=844));page.reload();expect(page.locator('#device-title')).to_be_visible()
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth+2')
        page.screenshot(path=str(a.output.with_suffix('.mobile.png')),full_page=True);checks.append('mobile_layout')
        # Actual service failures, checked in the DOM and against fresh authoritative API.
        sequence=ctx.request.get(url+'/api/monitoring/alpha').json()['items'][0]['telemetry']['sequence_number']
        try:
            d.run('stop','mongo');page.locator('#refresh').click()
            expect(page.locator('#history-status')).to_have_text('История временно недоступна',timeout=20000)
            expect(page.locator('#components .component').filter(has_text='PostgreSQL')).to_contain_text('Доступно')
            expect(page.locator('#components .component').filter(has_text='MQTT receiver')).to_contain_text('Готов')
            current=ctx.request.get(url+'/api/monitoring/alpha').json()
            assert current['items'][0]['telemetry']['sequence_number']>sequence
            assert current['components']['mongo']['status']=='unavailable'
        finally:d.run('up','-d','--no-deps','--wait','mongo')
        page.locator('#refresh').click();expect(page.locator('#history-status')).to_contain_text('измерений',timeout=20000)
        checks.append('real_mongo_outage_ui_independent_receiver')
        try:
            d.run('stop','control-worker')
            expect(page.locator('#components .component').filter(has_text='Control Worker')).to_contain_text('Устарело',timeout=25000)
            expect(page.locator('#switch-submit')).to_be_disabled()
            expect(page.locator('#device-status')).to_contain_text('Свежая')
        finally:d.run('up','-d','--no-deps','--wait','control-worker')
        checks.append('real_control_outage_receiver_continues')
        try:
            d.run('stop','policy-worker')
            expect(page.locator('#components .component').filter(has_text='Policy Worker')).to_contain_text('Устарело',timeout=45000)
            expect(page.locator('#device-policy')).to_contain_text('Устаревшая')
            expect(page.locator('#device-status')).to_contain_text('Свежая')
        finally:d.run('up','-d','--no-deps','--wait','policy-worker')
        checks.append('real_policy_outage_crypto_continues')
        try:
            d.run('stop','device-alpha')
            expect(page.locator('#device-status')).to_contain_text('Устарело',timeout=30000)
        finally:d.run('up','-d','--no-deps','--wait','device-alpha')
        expect(page.locator('#device-status')).to_contain_text('Свежая',timeout=20000)
        checks.append('real_device_stale_restart')
        try:
            d.run('stop','postgres')
            expect(page.locator('#snapshot-status')).to_contain_text('недоступно',timeout=20000)
            expect(page.locator('#switch-submit')).to_be_disabled()
            assert page.locator('#effective-profile').count()==0
        finally:d.run('up','-d','--no-deps','--wait','postgres')
        expect(page.locator('#effective-profile')).to_have_text('Ascon-AEAD128',timeout=25000)
        checks.append('real_postgres_outage_invalidates_browser_state')
        try:
            d.run('stop','broker')
            expect(page.locator('#components .component').filter(has_text='MQTT receiver')).to_contain_text('Недоступно',timeout=25000)
        finally:d.run('up','-d','--no-deps','--wait','broker')
        expect(page.locator('#components .component').filter(has_text='MQTT receiver')).to_contain_text('Готов',timeout=25000)
        checks.append('real_broker_recovery')
        d.run('restart','control-worker');page.reload()
        expect(page.locator('#effective-profile')).to_have_text('Ascon-AEAD128',timeout=20000)
        checks.append('worker_restart_authoritative_ui')
        # DOM boundary tests use genuine snapshot/history shapes, intercepted only for injection.
        api=ctx.request.get(url+'/api/monitoring/alpha').json();history=ctx.request.get(url+'/api/telemetry/history?device_id=alpha&limit=3').json()
        for payload in ['<img src=x onerror="window.__xss=1">','<svg onload="window.__xss=1"></svg>','" autofocus onfocus="window.__xss=1"','</script><script>window.__xss=1</script>']:
            value=copy.deepcopy(api)
            value['decisions']=[dict(result=dict(observed_risk='WATCH',reasons=[payload],used_signals=[]),created_at=api['checked_at'])]
            value['audit']=[dict(device_id='alpha',transition_id=value['transitions'][0]['id'],action=payload,at=api['checked_at'])]
            value['ml_events']=[dict(model_id=payload,model_version='test',status=payload,score=payload,threshold=None,evaluated_at=None)]
            page.route('**/api/monitoring/alpha?*',reply(value))
            page.reload();expect(page.locator('#policy-decisions')).to_contain_text(payload)
            assert page.locator('#monitoring img,#monitoring svg,#monitoring [onfocus]').count()==0
            assert page.evaluate('window.__xss || 0')==0
            page.unroute('**/api/monitoring/alpha?*')
        checks.append('four_dom_attribute_script_audit_ml_injections')
        for body in [None,{},dict(api,items=[dict(api['items'][0],device_id='beta')]),dict(api,items=[dict(api['items'][0],device_id='<img src=x onerror=window.__xss=1>')])]:
            page.route('**/api/monitoring/alpha?*',reply(body))
            page.reload();expect(page.locator('#snapshot-status')).to_contain_text('недоступно')
            expect(page.locator('#switch-submit')).to_be_disabled()
            assert page.locator('#effective-profile').count()==0
            page.unroute('**/api/monitoring/alpha?*')
        checks+=['malformed_api_fail_closed','other_device_snapshot_rejected']
        # Stale recommendation/telemetry/ACK-only truth checks in real DOM with controlled fixtures.
        value=copy.deepcopy(api);value['items'][0]['status']='stale';value['items'][0]['telemetry_age_seconds']=300
        value['items'][0]['reported_profile']='aes-128-gcm-v1'
        page.route('**/api/monitoring/alpha?*',lambda route:route.fulfill(json=value));page.reload()
        expect(page.locator('#device-status')).to_contain_text('Устарело')
        expect(page.locator('#effective-profile')).to_have_text('Ascon-AEAD128')
        expect(page.locator('#reported-profile')).to_have_text('AES-128-GCM')
        page.unroute('**/api/monitoring/alpha?*');checks+=['dom_stale_not_recent','dom_reported_not_effective']
        page.route('**/api/telemetry/history?*',lambda route:route.fulfill(status=503,json=dict(error='outage')))
        page.reload();expect(page.locator('#history-status')).to_have_text('История временно недоступна')
        checks.append('dom_mongo_unavailable_not_empty');page.unroute('**/api/telemetry/history?*')
        assert not errors,errors
        browser.close()
    a.output.write_text(json.dumps(dict(project=d.project,browser='Chromium via Playwright 1.56.0',real_crypto_switches=4 if isinstance(d,(KuzLab,ResearchLab)) else 2,
        checks=checks,page_errors=errors,commands=d.commands,fixture_injection_tests_separate=True,exit_code=0),indent=2)+'\n')
    print(json.dumps(dict(checks=checks,exit_code=0),indent=2))

if __name__=='__main__':main()

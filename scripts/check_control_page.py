"""Actual browser checks for the dedicated crypto page; optional real roundtrip.
Fixtures for DOM boundaries are separate from real MQTT/AEAD switching.
"""
import argparse
import copy
import json
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
from scripts.stage9_common import Demo


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--directory',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--roundtrip',action='store_true');a=p.parse_args()
    if a.output.exists():p.error('Immutable report exists')
    d=Demo(a.directory);url=d.url();checks=[];switches=0
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True)
        context=browser.new_context(viewport=dict(width=1366,height=900),timezone_id='Europe/Moscow')
        page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.route('https://cdn.**/*',lambda r:r.abort())
        def login(role):
            page.goto(url+'/login');page.locator('[name=username]').fill('demo-'+role)
            page.locator('[name=password]').fill((d.root/'accounts'/(role+'.password')).read_text().strip())
            page.locator('form input[type=submit],form button[type=submit]').first.click();page.wait_for_url(url+'/')
            page.goto(url+'/control');expect(page.locator('#crypto-effective')).not_to_have_text('Нет текущих данных',timeout=15000)
        def logout():
            page.locator('form[action="/logout"] button').click();page.wait_for_url('**/login')
        for role in ['viewer','operator']:
            login(role);expect(page.locator('h1')).to_have_text('Управление шифрованием')
            assert page.locator('#crypto-submit').count()==0
            assert page.locator('#device-rows').count()==0
            assert page.locator('canvas').count()==0
            expect(page.locator('#crypto-readonly')).to_be_visible()
            token=page.locator('meta[name="csrf-token"]').get_attribute('content')
            r=context.request.post(url+'/api/control/alpha/switch',headers={'X-CSRFToken':token},data=dict(profile='aes-128-gcm-v1',ttl=120))
            assert r.status==403
            checks.append(role+'_readonly_and_server_forbidden');logout()
        login('admin');expect(page.locator('#crypto-device option')).to_have_count(3)
        page.locator('#crypto-device').select_option('gamma')
        expect(page.locator('#crypto-state-title')).to_have_text('Состояние устройства gamma')
        expect(page.locator('#crypto-submit')).to_be_disabled()
        assert page.locator('#crypto-target option[value="aes-128-gcm-v1"]').count()==0
        checks.append('gamma_unsupported_disabled')
        page.locator('#crypto-device').select_option('alpha')
        expect(page.locator('#crypto-state-title')).to_have_text('Состояние устройства alpha')
        expect(page.locator('#crypto-submit')).to_be_enabled()
        requests=[]
        page.on('request',lambda r:requests.append(r.url) if r.method=='POST' and '/switch' in r.url else None)
        page.locator('#crypto-submit').click();expect(page.locator('#crypto-confirm')).to_be_visible()
        expect(page.locator('#crypto-device')).to_be_disabled()
        page.locator('#crypto-confirm button[value="cancel"]').click();expect(page.locator('#crypto-submit')).to_be_enabled()
        assert not requests
        checks.append('confirmation_cancel_sends_no_command')
        baseline=context.request.get(url+'/api/monitoring/alpha').json();original=baseline['items'][0]['effective_profile']
        assert original in ['ascon-aead128-v1','aes-128-gcm-v1']
        neighbors=context.request.get(url+'/api/monitoring').json()
        if a.roundtrip:
            targets=['aes-128-gcm-v1','ascon-aead128-v1'] if original=='ascon-aead128-v1' else ['ascon-aead128-v1','aes-128-gcm-v1']
            for target in targets:
                page.locator('#crypto-target').select_option(target)
                page.locator('#crypto-submit').click();page.locator('#crypto-confirm-submit').click()
                expect(page.locator('#crypto-request-message')).to_contain_text('Запрос сохранён',timeout=15000)
                expect(page.locator('#crypto-effective')).to_have_text(baseline['profiles'][target]['algorithm'],timeout=45000)
                expect(page.locator('#crypto-history')).to_contain_text('Authenticated ACK')
                expect(page.locator('#crypto-history')).to_contain_text('Подтверждающая AEAD-телеметрия')
                expect(page.locator('#crypto-submit')).to_be_enabled(timeout=15000)
                switches+=1
            final=context.request.get(url+'/api/monitoring/alpha').json()
            assert final['items'][0]['effective_evidence']['event_id']!=baseline['items'][0]['effective_evidence']['event_id']
            for t in final['transitions'][:2]:assert t['phase']=='EFFECTIVE_CONFIRMED' and t['telemetry_event'] and t['confirmed_at']
            current=context.request.get(url+'/api/monitoring').json()
            for name in ['beta','gamma']:
                before=next(x for x in neighbors['items'] if x['device_id']==name)
                after=next(x for x in current['items'] if x['device_id']==name)
                assert after['effective_profile']==before['effective_profile'] and after['effective_evidence']==before['effective_evidence']
            checks+=['real_roundtrip_with_receipts','neighbors_unchanged']
        page.reload();expect(page.locator('#crypto-effective')).to_have_text(baseline['profiles'][original]['algorithm'])
        assert page.locator('#crypto-device').input_value()=='alpha';checks.append('selection_and_state_survive_reload')
        a.output.parent.mkdir(parents=True,exist_ok=True)
        page.screenshot(path=str(a.output.with_suffix('.desktop.png')),full_page=True)
        page.set_viewport_size(dict(width=390,height=844));page.reload();expect(page.locator('#crypto-content')).to_be_visible()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+2')
        page.screenshot(path=str(a.output.with_suffix('.mobile.png')),full_page=True);checks.append('mobile_no_page_overflow')
        api=context.request.get(url+'/api/monitoring/alpha').json()
        def reply(value):return lambda route:route.fulfill(content_type='application/json',body=json.dumps(value))
        # ACK-only response must keep the old verified profile, even with a pending new target.
        fixture=copy.deepcopy(api);other='aes-128-gcm-v1' if original=='ascon-aead128-v1' else 'ascon-aead128-v1'
        fixture['items'][0]['reported_profile']=other
        if fixture['transitions']:
            t=copy.deepcopy(fixture['transitions'][0]);t.update(phase='DEVICE_APPLIED',target_profile=other,telemetry_event=None,confirmed_at=None,expired=False,deadline='2099-01-01T00:00:00+00:00')
            fixture['items'][0]['pending']=t;fixture['transitions']=[t]
        page.route('**/api/monitoring/alpha',reply(fixture));page.reload()
        expect(page.locator('#crypto-effective')).to_have_text(api['profiles'][original]['algorithm'])
        expect(page.locator('#crypto-reported')).to_have_text(api['profiles'][other]['algorithm'])
        expect(page.locator('#crypto-operation')).to_contain_text('ожидается подтверждение телеметрией')
        expect(page.locator('#crypto-submit')).to_be_disabled();page.unroute('**/api/monitoring/alpha')
        checks.append('ack_never_overwrites_verified_profile')
        fixture=copy.deepcopy(api);fixture['components']['control']['status']='stale'
        page.route('**/api/monitoring/alpha',reply(fixture));page.reload();expect(page.locator('#crypto-submit')).to_be_disabled()
        expect(page.locator('#crypto-worker')).to_contain_text('устарел');page.unroute('**/api/monitoring/alpha');checks.append('stale_worker_disables_request')
        for bad in [None,{},dict(api,items=[dict(api['items'][0],device_id='beta')]),dict(api,effective_evidence=None,commands=[dict(device_id='beta')])]:
            page.route('**/api/monitoring/alpha',reply(bad));page.reload()
            expect(page.locator('#crypto-message')).to_contain_text('недоступно')
            expect(page.locator('#crypto-content')).not_to_be_visible()
            page.unroute('**/api/monitoring/alpha')
        checks.append('malformed_and_cross_device_responses_invalidate')
        for payload in ['<img src=x onerror="window.__xss=1">','<svg onload="window.__xss=1"></svg>','" autofocus onfocus="window.__xss=1"','</script><script>window.__xss=1</script>']:
            fixture=copy.deepcopy(api)
            if fixture['transitions']:fixture['transitions'][0]['actor']=payload
            page.route('**/api/monitoring/alpha',reply(fixture));page.reload()
            expect(page.locator('#crypto-history')).to_contain_text(payload)
            assert page.locator('#crypto-control img,#crypto-control svg,#crypto-control [onfocus]').count()==0
            assert page.evaluate('window.__xss || 0')==0
            page.unroute('**/api/monitoring/alpha')
        checks.append('four_dom_injection_payloads_safe')
        assert not errors,errors
        browser.close()
    report=dict(checks=checks,real_transitions=switches,original_profile=original,controlled_dom_fixtures_separate=True,page_errors=errors,exit_code=0)
    a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':main()

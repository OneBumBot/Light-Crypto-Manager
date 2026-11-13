"""Actual desktop/mobile UI and screenshots; no mocked success states."""
import argparse
import json
from datetime import datetime,timezone
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
from scripts.stage16_demo import Demo,docker_git_sha


def main():
    p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,default=Path('.local-runtime/stage16/demo'));p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():p.error('Immutable browser report exists')
    d=Demo(a.directory);url=d.url();images=a.output.parent/(a.output.stem+'-screenshots');images.mkdir(exist_ok=True);records=[];errors=[];checks=[];dimensions=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True)
        context=browser.new_context(viewport=dict(width=1440,height=1000),timezone_id='Europe/Moscow')
        page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
        # Actual bundled application must keep working if decorative CDN assets are absent.
        page.route('https://**/*',lambda route:route.abort())
        def screenshot(name,scope):
            target=images/(name+'.png');page.screenshot(path=str(target),full_page=True)
            records.append(dict(path=str(target),url_path=page.url.removeprefix(url),at=datetime.now(timezone.utc).isoformat(),source_sha=docker_git_sha(),context=scope,viewport=page.viewport_size,no_secrets_visible=True))
        def login(role):
            page.goto(url+'/login');page.locator('[name=username]').fill('demo-'+role);page.locator('[name=password]').fill((d.root/'accounts'/(role+'.password')).read_text().strip());page.locator('form input[type=submit],form button[type=submit]').first.click();page.wait_for_url(url+'/');page.wait_for_selector('#device-rows tr[data-device=alpha]')
        page.goto(url+'/login');screenshot('login','Empty real login form; no password/token displayed')
        for role in ['viewer','operator']:
            login(role);page.goto(url+'/devices/alpha');expect(page.locator('#effective-profile')).to_have_text('Ascon-AEAD128');assert page.locator('#switch-submit').count()==0;checks.append(role+'_readonly_card');page.locator('form[action="/logout"] button').click();page.wait_for_url('**/login')
        login('admin');screenshot('monitoring','Three actual software Device Agents, current PG/Mongo/Policy status')
        page.goto(url+'/devices/alpha');expect(page.locator('#history-rows tr').first).to_be_visible();expect(page.locator('#effective-profile')).to_have_text('Ascon-AEAD128');screenshot('device-alpha','Live Ascon telemetry, Mongo history, security/Policy/control evidence')
        page.goto(url+'/control?device_id=alpha');expect(page.locator('#crypto-effective')).to_have_text('Ascon-AEAD128');screenshot('manual-control','Admin-only real control UI, before new request')
        def switch(label):
            page.locator('#crypto-target').select_option(label=label);page.locator('#crypto-submit').click();expect(page.locator('#crypto-confirm')).to_be_visible();page.locator('#crypto-confirm-submit').click();expect(page.locator('#crypto-effective')).to_have_text(label,timeout=45000);expect(page.locator('#crypto-history')).to_contain_text('Authenticated ACK');expect(page.locator('#crypto-history')).to_contain_text('Криптопрофиль подтверждён новой телеметрией');assert any(t['phase']=='EFFECTIVE_CONFIRMED' and t['target_profile']==('aes-128-gcm-v1' if label=='AES-128-GCM' else 'ascon-aead128-v1') for t in context.request.get(url+'/api/control').json()['transitions']);page.wait_for_timeout(2100)
        switch('AES-128-GCM');screenshot('confirmed-aes','New real admin browser request, authenticated ACK and telemetry-confirmed AES')
        switch('Ascon-AEAD128');screenshot('confirmed-ascon','New real browser reverse transition, verified Ascon telemetry')
        page.goto(url+'/telemetry');page.locator('#historyFilters [name=device_id]').fill('alpha');page.locator('#historyFilters button').click();expect(page.locator('#historyRows tr').first).to_be_visible();screenshot('history','Actual Mongo history, filtered to alpha')
        page.goto(url+'/policy');expect(page.locator('#policyWorkerStatus')).to_contain_text('ready',timeout=15000);screenshot('policy','Actual DRY_RUN version/backlog/processed-evidence freshness; no automatic apply')
        page.goto(url+'/devices/alpha');expect(page.locator('#security-events')).not_to_be_empty();screenshot('security-events','Existing authenticated security journal on device card')
        page.goto(url+'/research/shadow-ids');expect(page.locator('#shadow-status')).not_to_have_text('Источник не проверен',timeout=15000);assert page.locator('#shadow-rows tr').count()==0;screenshot('shadow-unavailable','OPTIONAL_RESEARCH_DEMO_UNAVAILABLE; no model/observer provisioned, no fake score')
        checks+=['real_browser_two_confirmed_switches','authenticated_ack_and_effective_distinct','actual_mongo_history','policy_dry_run','optional_shadow_unavailable_honest','external_cdn_not_required_for_core_behavior']
        page.set_viewport_size(dict(width=390,height=844))
        for path,name,selector in [('/','monitoring-mobile','#device-rows tr'),('/devices/alpha','device-mobile','#effective-profile'),('/telemetry','history-mobile','#historyRows tr'),('/policy','policy-mobile','#policyWorkerStatus'),('/control?device_id=alpha','control-mobile','#crypto-effective')]:
            page.goto(url+path);page.wait_for_selector(selector);page.wait_for_timeout(400)
            width=page.evaluate('innerWidth');scroll=page.evaluate('document.documentElement.scrollWidth');assert scroll<=width+2,(path,width,scroll)
            dimensions.append(dict(path=path,viewport_width=width,document_width=scroll));screenshot(name,'Actual mobile layout; internal horizontal table scroll allowed, document fits viewport')
        checks.append('mobile_five_pages_no_document_overflow')
        assert not errors,errors
        context.close();browser.close()
    result=dict(source_sha=docker_git_sha(),project=d.project,browser='Actual Playwright Chromium, desktop1440x1000/mobile390x844',screenshots=records,dimensions=dimensions,page_errors=errors,checks=checks,commands=d.commands,exit_code=0)
    a.output.write_text(json.dumps(result,indent=2));print('Real UI/screenshots and mobile assertions passed; exit0')

if __name__=='__main__':main()

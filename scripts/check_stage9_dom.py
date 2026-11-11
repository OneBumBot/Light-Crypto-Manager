"""Focused real Chromium DOM truth checks using controlled genuine API shapes.
No crypto switch is performed here. The full E2E runner proves real switching.
"""
import argparse,copy,json,re
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
from scripts.stage9_common import Demo


def main():
    p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,required=True);p.add_argument('--script',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    d=Demo(a.directory);url=d.url();checks=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True);context=browser.new_context();page=context.new_page()
        page.route('https://cdn.**/*',lambda route:route.abort())
        if a.script:page.route('**/static/js/monitoring.js',lambda route:route.fulfill(content_type='application/javascript',body=a.script.read_text()))
        page.goto(url+'/login');page.locator('[name=username]').fill('demo-admin');page.locator('[name=password]').fill((d.root/'accounts/admin.password').read_text().strip())
        page.locator('form input[type=submit],form button[type=submit]').first.click();page.wait_for_url(url+'/')
        api=context.request.get(url+'/api/monitoring/alpha').json()
        assert api['items'][0]['effective_profile']=='ascon-aead128-v1'
        fixture=copy.deepcopy(api);fixture['items'][0]['reported_profile']='aes-128-gcm-v1';fixture['items'][0]['status']='stale';fixture['items'][0]['telemetry_age_seconds']=300
        fixture['components']['control']['status']='stale';fixture['components']['policy']['status']='stale'
        fixture['items'][0]['policy']['stale']=True
        page.route('**/api/monitoring/alpha?*',lambda route:route.fulfill(json=fixture))
        page.route('**/api/telemetry/history?*',lambda route:route.fulfill(status=503,json=dict(error='controlled outage')))
        page.goto(url+'/devices/alpha');expect(page.locator('#effective-profile')).to_have_text('Ascon-AEAD128')
        expect(page.locator('#reported-profile')).to_have_text('AES-128-GCM')
        expect(page.locator('#device-status')).to_contain_text('Устарело')
        expect(page.locator('#history-status')).to_have_text('История временно недоступна')
        expect(page.locator('#switch-submit')).to_be_disabled()
        expect(page.locator('#device-policy')).to_contain_text('Устаревшая')
        checks=['ack_not_effective','stale_not_recent','mongo_failure_not_empty','stale_control_disables_submit','stale_policy_marked']
        browser.close()
    a.output.write_text(json.dumps(dict(checks=checks,controlled_fixtures=True,exit_code=0),indent=2)+'\n')
    print(json.dumps(dict(checks=checks,exit_code=0)))

if __name__=='__main__':main()

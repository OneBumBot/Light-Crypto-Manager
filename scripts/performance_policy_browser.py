"""Real DOM truth check for fresh worker heartbeat with stale Policy evidence."""
import argparse,json
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
from scripts.performance_lab import Lab


def main():
    p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():p.error('Immutable report exists')
    lab=Lab(a.directory);url=lab.url()
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True);context=browser.new_context(viewport=dict(width=1366,height=900));page=context.new_page();errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)));page.route('https://cdn.**/*',lambda route:route.abort())
        page.goto(url+'/login');page.locator('[name=username]').fill('demo-viewer');page.locator('[name=password]').fill((lab.root/'accounts/viewer.password').read_text().strip());page.locator('form input[type=submit],form button[type=submit]').first.click();page.wait_for_url(url+'/')
        page.goto(url+'/devices/alpha');expect(page.locator('#device-policy')).to_contain_text('DRY_RUN',timeout=20000)
        actual=context.request.get(url+'/api/monitoring/alpha').json();d=actual['items'][0];policy=d['policy']
        assert actual['components']['policy']['status']=='ready'
        assert policy['evidence_stale'] and policy['stale']
        assert policy['evidence_age_seconds']>policy['evidence_ttl_seconds']
        assert d['status']=='recent'
        expect(page.locator('#device-policy')).to_contain_text('Устаревшая')
        expect(page.locator('#device-policy')).to_contain_text('События устарели')
        expect(page.locator('#device-status')).to_contain_text('Свежая')
        assert page.locator('#switch-submit').count()==0
        page.screenshot(path=str(a.output.with_suffix('.png')),full_page=True)
        page.goto(url+'/policy');expect(page.locator('h1')).to_contain_text('DRY_RUN')
        assert page.locator('details.policy-panel[open]').count()==0
        assert not errors
        browser.close()
    a.output.write_text(json.dumps(dict(project=lab.project,devices=len(lab.devices),real_api=True,controlled_fixtures=False,policy_worker=actual['components']['policy'],policy=policy,telemetry_status=d['status'],checks=['fresh_heartbeat_does_not_refresh_old_evidence','stale_policy_real_dom','telemetry_remains_recent','viewer_cannot_control','policy_json_collapsed'],page_errors=errors,exit_code=0),indent=2))
    print('Real Policy backlog DOM truth checked, exit 0')

if __name__=='__main__':main()

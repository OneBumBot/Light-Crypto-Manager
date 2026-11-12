"""Real Chromium encryption-page journey; no API response substitution."""
import argparse,json,time,subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
from scripts.kuz_lab import Lab


def main():
    p=argparse.ArgumentParser();p.add_argument('--directory',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():p.error('Immutable output exists')
    lab=Lab(a.directory);url=lab.url();checks=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True);ctx=browser.new_context(viewport=dict(width=1366,height=900));page=ctx.new_page();errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.route('https://cdn.**/*',lambda route:route.abort())
        def login(role):
            page.goto(url+'/login');page.locator('[name=username]').fill('demo-'+role);page.locator('[name=password]').fill((lab.root/'accounts'/(role+'.password')).read_text().strip());page.locator('form input[type=submit],form button[type=submit]').first.click();page.wait_for_url(url+'/')
            page.goto(url+'/control');page.wait_for_selector('#crypto-device option[value=alpha]',state='attached');expect(page.locator('#crypto-device')).to_be_enabled();page.locator('#crypto-device').select_option('alpha')
        login('viewer');expect(page.locator('#crypto-effective')).to_have_text('Ascon-AEAD128',timeout=15000);assert page.locator('#crypto-submit').count()==0
        checks.append('viewer_encryption_page_read_only');page.locator('form[action="/logout"] button').click();page.wait_for_url('**/login')
        login('admin');expect(page.locator('#crypto-effective')).to_have_text('Ascon-AEAD128',timeout=15000)
        receipts=[]
        for profile,label in [('kuznyechik-mgm-v1','Kuznyechik-MGM'),('aes-128-gcm-v1','AES-128-GCM'),('kuznyechik-mgm-v1','Kuznyechik-MGM'),('ascon-aead128-v1','Ascon-AEAD128')]:
            time.sleep(2.1);page.locator('#crypto-target').select_option(profile);page.locator('#crypto-submit').click();expect(page.locator('#crypto-confirm')).to_be_visible();page.locator('#crypto-confirm-submit').click()
            expect(page.locator('#crypto-effective')).to_have_text(label,timeout=45000)
            expect(page.locator('#crypto-effective-note')).to_contain_text('принятой AEAD')
            value=ctx.request.get(url+'/api/monitoring/alpha').json()['items'][0]
            assert value['effective_profile']==profile and value['effective_evidence']['event_id'];receipts.append(value['effective_evidence'])
            page.reload();expect(page.locator('#crypto-effective')).to_have_text(label,timeout=15000)
        checks.append('four_real_control_page_switches_receipt_only')
        page.locator('#crypto-device').select_option('gamma');expect(page.locator('#crypto-state-title')).to_have_text('Состояние устройства gamma');expect(page.locator('#crypto-effective')).to_have_text('Ascon-AEAD128')
        assert page.locator('#crypto-target option[value=kuznyechik-mgm-v1]').count()==0;expect(page.locator('#crypto-submit')).to_be_disabled();checks.append('gamma_capability_bound')
        page.locator('#crypto-device').select_option('beta');expect(page.locator('#crypto-state-title')).to_have_text('Состояние устройства beta');expect(page.locator('#crypto-effective')).to_have_text('Ascon-AEAD128');checks.append('neighbor_unaffected')
        assert not errors;browser.close()
    a.output.write_text(json.dumps(dict(project=lab.project,source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),checks=checks,real_crypto_switches=4,effective_receipts=receipts,page_errors=errors,exit_code=0),indent=2))
    print('Real control-page browser journey: exit 0')

if __name__=='__main__':main()

"""Run the actual table JS in Chromium, exercising record-to-DOM boundaries."""
import json
from pathlib import Path
import re
from playwright.sync_api import sync_playwright

root=Path(__file__).resolve().parents[1]
source=(root/'src/web/templates/table_edit.html').read_text()
script=re.search(r'<script>\s*(.*?)</script>',source,re.S).group(1)
values={'table_name':'algorithms','primary_keys':['Algorithm_ID'],
        'columns':['Algorithm_ID','Algorithm_Name'],'field_types':{'Algorithm_ID':'int','Algorithm_Name':'str'}}
for key,value in values.items():
    script=re.sub(r'{{\s*'+key+r'\s*\|\s*tojson\s*}}',json.dumps(value),script)
assert '{{' not in script
with sync_playwright() as playwright:
    browser=playwright.chromium.launch(headless=True)
    page=browser.new_page()
    page.route('**/*',lambda route: route.abort())
    page.set_content('<meta name="csrf-token" content="test">'+''.join(
        '<div id="'+name+'"></div>' for name in ['formFields','modalTitle','formError',
        'viewModalBody','viewModal','editModal','deleteRecordInfo','deleteModal']))
    page.add_script_tag(content='window.bootstrap={Modal:class { show(){} static getInstance(){return {hide(){}}} }};'+script)
    for payload in ['<img src=x onerror="window.__xss=1">',
                    '<svg onload="window.__xss=1"></svg>',
                    '\" autofocus onfocus="window.__xss=1" x="',
                    '</script><script>window.__xss=1</script>']:
        page.evaluate('''(payload) => {
            const record={Algorithm_ID:1, Algorithm_Name:payload};
            viewRecord(record); editRecord(record); deleteRecord(record);
            showNotification('success', payload);
        }''',payload)
        assert page.locator('#field_Algorithm_Name').input_value()==payload
        assert page.locator('#field_Algorithm_Name').get_attribute('onfocus') is None
        assert payload in page.locator('#viewModalBody').inner_text()
        assert page.locator('img,svg').count()==0
        assert page.evaluate('window.__xss || 0')==0
    ml_source=(root/'src/web/static/js/ml_results.js').read_text()
    for payload in ['<img src=x onerror="window.__xss=1">', '<svg onload="window.__xss=1"></svg>',
                    '\" autofocus onfocus="window.__xss=1" x="', '</script><script>window.__xss=1</script>']:
        ml_page=browser.new_page()
        ml_page.set_content('<form id="mlFilters"><input name="device_id"></form>'+''.join(
            '<div id="'+name+'"></div>' for name in ['mlStatus','protocolStatus','rulesStatus','mlMessage'])+
            '<table><tbody id="mlRows"></tbody></table>')
        ml_page.evaluate("""(payload) => {
            const record={device_id:payload,detector:payload,evaluated_at:payload,score:payload,
                threshold:payload,model_id:payload,model_version:payload,status:payload,is_anomaly:null};
            window.fetch=async url => ({ok:true,json:async()=>url.startsWith('/api/ml/events')
                ? {items:[record]} : {models:[{diagnostic:payload}],feed:{},event_status_counts:{},
                    protocol_rejections:payload,rule_anomalies:payload}});
        }""",payload)
        ml_page.add_script_tag(content=ml_source)
        ml_page.wait_for_selector('#mlRows tr')
        assert payload in ml_page.locator('#mlRows').inner_text()
        assert ml_page.locator('img,svg').count()==0
        assert ml_page.evaluate('window.__xss || 0')==0
        ml_page.close()
    policy_source=(root/'src/web/static/js/policy.js').read_text()
    for payload in ['<img src=x onerror="window.__xss=1">','<svg onload="window.__xss=1"></svg>',
                    '</script><script>window.__xss=1</script>','" autofocus onfocus="window.__xss=1"']:
        policy_page=browser.new_page()
        policy_page.set_content('<form id="policyFilters"><input name="device_id"></form>'+''.join(
            '<pre id="'+name+'"></pre>' for name in ['policyMessage','policyOverview','policyDecisions',
                'policySignals','policyTransitions','policyIntents']))
        policy_page.evaluate("""payload => {
            window.fetch=async () => ({ok:true,json:async()=>({items:[{reason:payload,requested:payload,applied:null}]})});
        }""",payload)
        policy_page.add_script_tag(content=policy_source)
        policy_page.wait_for_function("document.getElementById('policyIntents').textContent.length>0")
        import json
        assert json.loads(policy_page.locator('#policyOverview').inner_text())['items'][0]['reason']==payload
        assert policy_page.locator('img,svg').count()==0
        assert policy_page.evaluate('window.__xss || 0')==0
        policy_page.close()
    browser.close()
print('PASS: real Chromium rejects DOM/attribute/script injection in view, edit, delete and notification flows (4 payloads)')

print('PASS: real Chromium renders ML scores/status/model metadata as text (4 injection payloads)')

print('PASS: Chromium policy reasons/source/configuration injection rendered as text (4 payloads)')

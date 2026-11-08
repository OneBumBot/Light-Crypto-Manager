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
    browser.close()
print('PASS: real Chromium rejects DOM/attribute/script injection in view, edit, delete and notification flows (4 payloads)')

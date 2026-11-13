"""Actual Flask/Chromium Shadow journey, plus explicitly separate DOM fault fixtures."""
import argparse,json,os,secrets,threading,time
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
from scripts.stage15_setup import lab
from scripts.stage15_runs import send,capture,workload,wait
from scripts.stage15_performance import start_worker

def main():
 p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,default=Path('.local-runtime/stage15/online'));p.add_argument('--run',default='browser-live-v3');a=p.parse_args();l=lab(a.directory);report=Path('docs/reports/stage15/browser.json')
 if report.exists():raise ValueError('Immutable browser report')
 # Only after collection: loopback-only host UI port, never public bind.
 private=l.root/'stage15.compose.json';cfg=json.loads(private.read_text());cfg['services']['web']={'ports':[],'environment':{'WEB_MQTT_ENABLED':'0'},'group_add':[str(os.getgid())],'volumes':[str(Path('src/shadow_ids').resolve())+':/app/src/shadow_ids:ro',str(Path('src/web/static/js/shadow_ids.js').resolve())+':/app/src/web/static/js/shadow_ids.js:ro',str(Path('src/web/templates/shadow_ids.html').resolve())+':/app/src/web/templates/shadow_ids.html:ro']};private.write_text(json.dumps(cfg,indent=2))
 accounts=l.root/'accounts';accounts.mkdir(mode=0o700,exist_ok=True);credentials={}
 for role in ['admin','operator','viewer']:
  path=accounts/(role+'.password')
  if not path.exists():path.write_text(secrets.token_urlsafe(30));path.chmod(0o600)
  credentials[role]=path.read_text()
 program="import sys,json;from src.web.app import app;from src.web.models import db,User\nwith app.app_context():\n for role,password in json.load(sys.stdin).items():\n  old=User.query.filter_by(username='shadow-'+role).first()\n  if old:\n   assert old.check_password(password) and old.role==role\n  else:\n   user=User(username='shadow-'+role,email=role+'@shadow.invalid',role=role);user.set_password(password);db.session.add(user)\n db.session.commit()\nprint('Accounts committed; passwords withheld')"
 send(l,['run','--rm','-T','--no-deps','tests','python','-c',program],credentials)
 name=a.run;cid=capture(l,name,condition='all',duration=35);wid=start_worker(l,name,['rf_binary','if','rf_session','if_session']);thread=threading.Thread(target=lambda:workload(l,name,3,.5,duration=20,seed=15901));thread.start();os.environ['SHADOW_RUN']=name;l.run('up','-d','--no-deps','--wait','web',timeout=90);cid_web=l.run('ps','-q','web').stdout.strip();inspected=json.loads(__import__('subprocess').check_output(['docker','inspect',cid_web],text=True))[0];address=next(iter(inspected['NetworkSettings']['Networks'].values()))['IPAddress'];assert __import__('ipaddress').ip_address(address).is_private and not any(inspected['NetworkSettings']['Ports'].values());url='http://'+address+':5000';checks=[];errors=[]
 with sync_playwright() as pw:
  browser=pw.chromium.launch(headless=True);ctx=browser.new_context();page=ctx.new_page();page.on('pageerror',lambda e:errors.append(str(e)));page.route('https://cdn.**/*',lambda route:route.abort())
  page.goto(url+'/login');page.locator('[name=username]').fill('shadow-viewer');page.locator('[name=password]').fill(credentials['viewer']);page.locator('form input[type=submit],form button[type=submit]').first.click();page.wait_for_url(url+'/');page.goto(url+'/research/shadow-ids');expect(page.locator('#shadow-rows tr').first).to_be_visible(timeout=20000);real=ctx.request.get(url+'/api/research/shadow-ids').json();assert real['available'] and real['results'] and all(r['trusted_detector'] is False and r['device_binding']=='unbound' for r in real['results']);page.screenshot(path=str(report.with_suffix('.png')),full_page=True);checks.append('genuine-live-journal-model-scores-visible')
  assert ctx.request.post(url+'/api/research/shadow-ids',data={}).status in [400,405];checks.append('viewer-no-control-post')
  payload=json.loads(json.dumps(real));attack='<img id="shadow-xss" src=x onerror="window.shadowInjected=1">';payload['results'][0]['model_id']=attack;page.route('**/api/research/shadow-ids?*',lambda route:route.fulfill(json=payload));page.reload();expect(page.locator('#shadow-rows')).to_contain_text(attack);assert page.locator('#shadow-xss').count()==0 and not page.evaluate('window.shadowInjected || 0');checks.append('controlled-dom-xss-no-execution')
  page.unroute('**/api/research/shadow-ids?*');page.route('**/api/research/shadow-ids?*',lambda route:route.fulfill(status=503,json={'available':False,'results':[]}));expect(page.locator('#shadow-rows tr')).to_have_count(0,timeout=10000);checks.append('controlled-source-failure-clears-old-scores');page.unroute('**/api/research/shadow-ids?*')
  l.run('stop','postgres');expect(page.locator('#shadow-status')).to_contain_text('Источник недоступен',timeout=15000);expect(page.locator('#shadow-rows tr')).to_have_count(0);checks.append('actual-pg-outage-no-current-score');l.run('up','-d','--no-deps','--wait','postgres',timeout=90)
  thread.join(30);wait(cid);wait(wid);time.sleep(6);page.reload();expect(page.locator('#shadow-rows tr')).to_have_count(0);checks.append('actual-finished-source-stale-clears-scores')
  browser.close()
 assert not errors,errors
 report.write_text(json.dumps(dict(checks=checks,real_api_packet_count=real['packets'],real_api_results=len(real['results']),browser_errors=errors,dom_fixtures_explicit=True,network_scope='Host direct private Docker IP, no published ports',no_host_ports=True,source_sha=__import__('subprocess').check_output(['git','rev-parse','HEAD'],text=True).strip(),exit_code=0),indent=2));print('Actual Chromium Shadow journey and separate XSS/outage fixtures: exit0')
if __name__=='__main__':main()

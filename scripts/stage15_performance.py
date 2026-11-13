"""Preregistered bounded same-host operational series; no model fitting/quality tuning."""
import argparse,hashlib,json,os,platform,subprocess,threading,time
from pathlib import Path
import numpy as np
from scripts.stage15_setup import lab
from scripts.stage15_runs import capture,workload,wait
from src.shadow_ids.journal import Journal

def state(l):
 r=l.run('run','--rm','-T','--no-deps','-e','RESEARCH_SINCE='+str(time.time()-60),'tests','python','-m','scripts.stand_state',timeout=60);return json.loads(r.stdout[r.stdout.index('{'):])
class Monitor:
 def __init__(self,l):self.l=l;self.done=threading.Event();self.rows=[];self.thread=threading.Thread(target=self.run,daemon=True)
 def run(self):
  while not self.done.is_set():
   ids=subprocess.check_output(['docker','ps','-q','--filter','label=com.docker.compose.project='+self.l.project],text=True).split()
   if ids:
    p=subprocess.run(['docker','stats','--no-stream','--format','{{json .}}',*ids],capture_output=True,text=True,timeout=15)
    self.rows.append(dict(at=time.time(),exit_code=p.returncode,containers=[json.loads(s) for s in p.stdout.splitlines() if s.startswith('{')]))
   self.done.wait(1)
 def start(self):self.thread.start()
 def stop(self):self.done.set();self.thread.join(20)

def start_worker(l,name,roles):
 return l.run('run','-d','--no-deps','--name',l.project+'-'+name+'-worker','shadow-model-worker','python','-m','src.shadow_ids.worker','--root','/shadow/'+name,'--models','/models','--parity','/parity.json','--roles',*roles,'--duration','60').stdout.strip().splitlines()[-1]

def distribution(values):
 if not values:return {'status':'not_measured'}
 v=np.array(values);return dict(n=len(v),mean=float(v.mean()),median=float(np.median(v)),std=float(v.std()),min=float(v.min()),max=float(v.max()),p95=float(np.quantile(v,.95)) if len(v)>=100 else None,p99=float(np.quantile(v,.99)) if len(v)>=1000 else None)

def run(l,name,n,interval,condition):
 report=Path('docs/reports/stage15')/(name+'.json')
 if report.exists():raise ValueError('Existing experiment preserved')
 before=state(l);monitor=Monitor(l);cid=None;wid=None;started=time.time();monitor.start()
 try:
  if condition!='off':cid=capture(l,name,condition=condition,duration=23)
  if condition in ['rf','rfif','all']:
   roles=['rf_binary'] if condition=='rf' else ['rf_binary','if'] if condition=='rfif' else ['rf_binary','if','rf_session','if_session'];wid=start_worker(l,name,roles)
  truth=workload(l,name,n,interval,seed=15000+sum(name.encode()))
  if cid:wait(cid)
  if wid:wait(wid)
 finally:monitor.stop()
 after=state(l);deadline=time.monotonic()+20
 while after['outbox_pending'] and time.monotonic()<deadline:time.sleep(.25);after=state(l)
 counters=json.loads(l.run('exec','-T','lab-devices','cat','/research/'+name+'/stage15-counters.json').stdout);root=l.root/'shadow'/name;counts={};timings={};capture_status=None
 if cid:
  capture_status=json.loads((root/'capture-status.json').read_text());db=Journal(root/'shadow.db',readonly=True);counts=dict(events=db.db.execute('select count(*) from events').fetchone()[0],results=db.db.execute('select count(*) from results').fetchone()[0],pending=len(db.pending(limit=50000)),inference_statuses=dict(db.db.execute("select json_extract(value,'$.inference_status'),count(*) from results group by 1").fetchall()),supported_packets=db.db.execute("select count(*) from events where json_extract(packet,'$.status')='FEATURE_READY'").fetchone()[0],session_count=db.db.execute("select count(distinct json_extract(packet,'$.session')) from events").fetchone()[0]);db.close()
  if (root/'commit-timings.jsonl').exists():
   raw=[json.loads(s) for s in (root/'commit-timings.jsonl').read_text().splitlines()];timings={key:distribution([r[end]-r[begin] for r in raw]) for key,begin,end in [('capture_to_feature','capture_timestamp','feature_ready_at'),('capture_to_prediction','capture_timestamp','inference_finish'),('model_batch_wall','inference_start','inference_finish'),('capture_to_journal_ack','capture_timestamp','journal_commit_ack_at')]}
  db=Journal(root/'shadow.db',readonly=True);alerts={}
  for r in db.db.execute('select value from results'):
   x=json.loads(r[0]);v=alerts.setdefault(x['model_role'],dict(scored=0,above_threshold=0));v['scored']+=int(x['inference_status']=='SCORED');v['above_threshold']+=int(x['comparison'] is True)
  db.close()
  for v in alerts.values():v['alerts_per_1000_scored_packets']=1000*v['above_threshold']/v['scored'] if v['scored'] else None
  counts['unlabelled_alert_rates']=alerts
 report_value=dict(experiment_id=name,source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),code_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('src/shadow_ids').glob('*.py')},condition=condition,device_identities=n,target_hz=1/interval,duration=15,started_at=started,finished_at=time.time(),counters=counters,generator_errors=truth['errors'],pg_accepted_delta=after['categories'].get('accepted',0)-before['categories'].get('accepted',0),pg_category_deltas={k:v-before['categories'].get(k,0) for k,v in after['categories'].items()},mongo_stored_delta=after['mongo_records']-before['mongo_records'],outbox_pending_after=after['outbox_pending'],capture=capture_status,shadow=counts,timings_seconds=timings,resources=monitor.rows,FPR='not_evaluable_unlabelled_operational_series',independent_host_domain='not_verified',generalization_evaluation='BLOCKED_INDEPENDENT_DATA',clock_model='same-host capture CLOCK_REALTIME and Python CLOCK_REALTIME; runtime monotonic watchdog, not cross-host clock proof',exit_code=0)
 if condition in ['rf','rfif','all'] and (counts.get('inference_statuses',{}).get('INFERENCE_ERROR') or counts.get('inference_statuses',{}).get('MODEL_UNAVAILABLE') or not counts.get('inference_statuses',{}).get('SCORED')):report_value['exit_code']=2
 report.write_text(json.dumps(report_value,indent=2))
 if report_value['exit_code']:raise RuntimeError('Online inference unavailable/error; failed measurements retained, stop expansion')
 print(name,'PG',report_value['pg_accepted_delta'],'Mongo',report_value['mongo_stored_delta'],'shadow',counts.get('results'),flush=True);return report_value

def main():
 p=argparse.ArgumentParser();p.add_argument('action',choices=['sanity','matrix']);p.add_argument('--directory',type=Path,default=Path('.local-runtime/stage15/online'));p.add_argument('--series',default='v2');a=p.parse_args();l=lab(a.directory)
 if a.action=='sanity':run(l,a.series+'-integration-four-models',3,.5,'all');return
 results=[]
 for cohort,n,interval in [('base',3,2),('small',10,1),('medium',25,.5),('extended',50,.5)]:
  for repeat in range(3):
   order=['off','capture','rf','rfif'];order=order[repeat:]+order[:repeat]
   for condition in order:
    name=f'{a.series}-{cohort}-r{repeat}-{condition}';path=Path('docs/reports/stage15')/(name+'.json')
    r=json.loads(path.read_text()) if path.exists() else run(l,name,n,interval,condition);results.append(r)
    if r['generator_errors'] or (r['capture'] and not r['capture']['complete']):raise RuntimeError('Stop expansion on actual source/resource failure; measurements retained')
 Path('docs/reports/stage15/performance-series.json').write_text(json.dumps(dict(runs=[r['experiment_id'] for r in results],independent_repeats=3,interpretation='same-host short operational repeated runs, not causal or generalization proof',exit_code=0),indent=2))
if __name__=='__main__':main()

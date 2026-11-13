"""Execute a frozen bounded Stage14 acquisition plan. Never trains or opens models."""
import argparse,hashlib,json,os,platform,subprocess,time
from pathlib import Path
from datetime import datetime,timezone
from scripts.stage14_lab import Lab as Infrastructure
from src.research_stand.orchestrator import Lab
from src.research_stand.config import Experiment
from src.research_stand.pcap_audit import headers,digest,load_json


def check_source(folder):
 rows,cap,ext=headers(folder);truth=load_json(folder/'ground-truth.json');observer=load_json(folder/'mqtt-observer.json');broker=load_json(folder/'broker-evidence.json');core=load_json(folder/'core.json')
 if truth['errors'] or not truth['all_clients_stopped'] or any(not r.get('closed_at') for r in truth['connections']):raise ValueError('Incomplete generator')
 if not observer.get('completed') or not observer.get('ready_observed') or observer.get('overflow') or observer.get('disconnected_unexpectedly'):raise ValueError('Incomplete independent observer')
 if broker.get('source')!='docker_mosquitto_log' or not broker.get('sessions'):raise ValueError('Missing broker session evidence')
 if core.get('postgres')!='available' or core.get('mongo')!='available':raise ValueError('Corroboration storage unavailable')
 return dict(packets=len(rows),pcap_sha256=cap['pcap_sha256'],observer_events=len(observer['events']),broker_sessions=len(broker['sessions']),source_hashes={p.name:digest(p) for p in folder.iterdir() if p.is_file() and p.name!='acquisition.json'})


def collect(lab_root,output,items,plan_sha,group,partition):
 infra=Infrastructure(lab_root);lab=Lab(infra.env,output,compose_overrides=[infra.root/'stage14.compose.json']);records=[]
 image_ids=json.loads(infra.run('images','--format','json').stdout);code_hashes={str(p):digest(p) for p in Path('src/research_stand').glob('*.py')};host=hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest()
 for item in items:
  cfg=Experiment(**item);folder=Path(output)/cfg.experiment_id
  if folder.exists():raise ValueError('Immutable experiment already exists; no automatic retry/rename')
  start=datetime.now(timezone.utc).isoformat();status='complete';detail=None;proof={}
  try:
   lab.experiment(cfg);proof=check_source(folder)
  except (ValueError,RuntimeError,subprocess.SubprocessError) as e:
   status='quarantined';detail=type(e).__name__+':'+str(e)[:200]
   if not folder.exists():
    subprocess.run(['docker','cp',lab.collector+':/research/'+cfg.experiment_id,str(folder)],capture_output=True,timeout=15)
   folder.mkdir(exist_ok=True,parents=True,mode=0o700)
  record=dict(experiment_id=cfg.experiment_id,status=status,diagnostic=detail,group=group,partition=partition,project=infra.project,host_identity_sha256=host,physical_host_count=1,plan_sha256=plan_sha,config=cfg.payload(),started_at=start,finished_at=datetime.now(timezone.utc).isoformat(),source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),source_code_hashes=code_hashes,images=image_ids,python=platform.python_version(),platform=platform.platform(),collector_position='lab-devices eth0',tls=True,**proof)
  (folder/'acquisition.json').write_text(json.dumps(record,indent=2))
  for p in [folder,*folder.rglob('*')]:p.chmod(0o700 if p.is_dir() else 0o600)
  records.append(record);print(cfg.experiment_id,status,proof.get('packets','not_measured'),flush=True)
 return records


def main():
 p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,required=True);p.add_argument('--captures',type=Path,required=True);p.add_argument('--plan',type=Path,default=Path('docs/reports/stage14/collection-plan.json'));p.add_argument('--pilot',action='store_true');p.add_argument('--block',type=int);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():p.error('Immutable run report')
 plan=json.loads(a.plan.read_text());given=plan.pop('sha256');assert hashlib.sha256(json.dumps(plan,sort_keys=True).encode()).hexdigest()==given
 if a.pilot:items=plan['pilot'];group='pilot';partition='excluded_pilot'
 else:
  group=f'block-{a.block:02}';selected=[r for r in plan['primary'] if r['group']==group];assert len(selected)==2;items=[r['config'] for r in selected];partition=selected[0]['partition']
 records=collect(a.directory,a.captures,items,given,group,partition);a.output.write_text(json.dumps(dict(records=records,exit_code=0 if all(r['status']=='complete' for r in records) else 2),indent=2));raise SystemExit(0 if all(r['status']=='complete' for r in records) else 2)
if __name__=='__main__':main()

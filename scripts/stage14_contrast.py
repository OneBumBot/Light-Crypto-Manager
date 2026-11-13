"""Real QoS1/replay/invalid-metadata contrast; no model inference or new positive claims."""
import argparse,json,subprocess,time
from pathlib import Path
import pandas as pd
from scripts.stage14_lab import Lab as Infrastructure
from src.research_stand.orchestrator import Lab
from src.research_stand.config import Experiment
from src.research_stand.dataset_v2 import build
from scripts.stage14_collect import check_source


def main():
 p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,default=Path('.local-runtime/stage14/contrast'));p.add_argument('--output',type=Path,default=Path('docs/reports/stage14/transport-contrast.json'));a=p.parse_args()
 if a.output.exists():p.error('Immutable report')
 infra=Infrastructure(a.directory);root=Path('.local-runtime/stage14/contrast-captures');lab=Lab(infra.env,root,compose_overrides=[infra.root/'stage14.compose.json']);records=[]
 for i,kind in enumerate(['qos1_retry','replay','wrong_epoch','wrong_sequence','tampered','broker_reconnect','receiver_restart']):
  name='contrast-'+kind.replace('_','-');original=lab.resource_usage;counter=[0];before=lab.state(time.time()-30);status='complete';diagnostic=None
  def resources():
   value=original();counter[0]+=1
   if counter[0]==2 and kind in ['broker_reconnect','receiver_restart']:infra.run('restart','broker' if kind=='broker_reconnect' else 'receiver')
   return value
  lab.resource_usage=resources
  try:
   lab.experiment(Experiment(name,kind if kind not in ['broker_reconnect','receiver_restart'] else 'regular',4,6,.45,.02,149100+i,kind in ['replay','wrong_epoch','wrong_sequence','tampered']));check_source(root/name)
  except (ValueError,RuntimeError,KeyError,TypeError,OSError,subprocess.SubprocessError) as e:
   status='quarantined';diagnostic=type(e).__name__+':'+str(e)[:160];folder=root/name
   if not folder.exists():subprocess.run(['docker','cp',lab.collector+':/research/'+name,str(folder)],capture_output=True,timeout=15)
  finally:lab.resource_usage=original
  end=time.monotonic()+60
  while time.monotonic()<end:
   after=lab.state(time.time()-30)
   if after['outbox_pending']==0:break
   time.sleep(.5)
  assert after['outbox_pending']==0
  labels=None;dups=None;actor=None
  if status=='complete':
   # Build one isolated analysis view, never merge into the frozen primary dataset.
   import shutil
   copy=Path('.local-runtime/stage14/contrast-views')/name;copy.mkdir(parents=True,mode=0o700);shutil.copytree(root/name,copy/name);out=copy/'dataset';build(copy,out);rows=pd.read_csv(out/'observations.csv',keep_default_na=False);labels={str(k):int(v) for k,v in rows.ground_truth.value_counts().items()};truth=json.loads((root/name/'ground-truth.json').read_text());actor_ids={r['connection_id'] for r in truth['connections'] if r['activity'] not in ['normal']};actor_rows=rows.loc[rows.connection_id.isin(actor_ids)];actor=dict(rows=len(actor_rows),labels={str(k):int(v) for k,v in actor_rows.ground_truth.value_counts().items()});broker=json.loads((root/name/'broker-evidence.json').read_text());dups=sum(e.get('dup')==1 for s in broker['sessions'] for e in s['events'])
   if kind=='qos1_retry':assert dups and not rows.ground_truth.eq('controlled_violation').any()
   if kind=='replay':assert rows.ground_truth.eq('controlled_violation').any()
   if kind in ['wrong_epoch','wrong_sequence','tampered']:assert actor_rows.ground_truth.eq('unknown').all() and after['categories'].get('rejected',0)>before['categories'].get('rejected',0)
  record=dict(case=kind,status=status,diagnostic=diagnostic,labels=labels,actor=actor,broker_dup_events=dups,category_deltas={k:after['categories'].get(k,0)-before['categories'].get(k,0) for k in set(after['categories'])|set(before['categories'])},outbox_pending_after=after['outbox_pending'],no_model_predictions=True,not_a_new_training_source=True);records.append(record);print(kind,status,labels,flush=True)
 a.output.write_text(json.dumps(dict(project=infra.project,cases=records,inference_performed=False,scientific_training_dataset_unchanged=True,interpretation='Transport duplicates do not prove malicious replay; application evidence is outside X',commands=infra.commands,exit_code=0),indent=2))
 infra.stop()
if __name__=='__main__':main()

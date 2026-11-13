"""Plots from actual saved repeated runs only; no inference, fit or threshold tuning."""
import argparse,json,re,subprocess
from pathlib import Path
import numpy as np,pandas as pd
from scripts.stage15_setup import lab
from scripts.stage15_runs import send
from src.shadow_ids.journal import Journal,path_for

def main():
 p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,default=Path('.local-runtime/stage15/online'));a=p.parse_args();l=lab(a.directory);base=Path('docs/reports/stage15');series=json.loads((base/'performance-series.json').read_text());runs=[json.loads((base/(n+'.json')).read_text()) for n in series['runs']]
 if len(runs)!=48:raise ValueError('Do not represent partial matrix as complete')
 program="import json;from pathlib import Path;rows=[]\nfor p in Path('/research').glob('v3-*/ground-truth.json'):\n r=json.loads(p.read_text());rows.append({'run':p.parent.name,'start':r['experiment_started_at'],'end':r['experiment_finished_at'],'seed':r['experiment']['seed'],'identities':list({(v['logical_device'],v['key_epoch'],v['sequence_number']) for v in r['messages']})})\nprint(json.dumps(rows))"
 windows=json.loads(l.run('exec','-T','lab-devices','python','-c',program).stdout);lookup={r['run']:r for r in windows};(base/'source-window-audit.json').write_text(json.dumps(dict(windows=[{k:v for k,v in r.items() if k!='identities'} for r in windows],scope='Actual driver wall windows used to crop resource samples equally across conditions, no model selection',exit_code=0),indent=2));rows=[]
 program="import sys,json;from sqlalchemy import create_engine,select,func,tuple_,text;from src.runtime import database_url;from src.outbox import outbox;from src.mongo_repository import MongoRepository;e=create_engine(database_url());repo=MongoRepository();runs=json.load(sys.stdin);result={}\nwith e.connect() as c:\n c.execute(text('SET TRANSACTION READ ONLY'))\n for name,ids in runs.items():\n  sub=select(outbox.c.created_at,outbox.c.delivered_at).where(tuple_(outbox.c.device_id,outbox.c.key_epoch,outbox.c.sequence_number).in_(ids)).subquery();delay=func.extract('epoch',sub.c.delivered_at-sub.c.created_at);n,mean,p50,p95,p99=c.execute(select(func.count(),func.avg(delay),func.percentile_cont(.5).within_group(delay),func.percentile_cont(.95).within_group(delay),func.percentile_cont(.99).within_group(delay)).select_from(sub)).one();mongo=repo.collection.count_documents({'_id':{'$in':[str(d)+':'+str(k)+':'+str(s) for d,k,s in ids]}},maxTimeMS=2000);result[name]=dict(known_published_identities=len(ids),pg_committed=n,mongo_stored=mongo,outbox_creation_to_delivered_marker_seconds=dict(mean=float(mean) if mean is not None else None,median=p50,p95=p95 if n>=100 else None,p99=p99 if n>=1000 else None))\nrepo.close();e.dispose();print(json.dumps(result))"
 exact=json.loads(send(l,['run','--rm','-T','--no-deps','tests','python','-c',program],{r['experiment_id']:lookup[r['experiment_id']]['identities'] for r in runs}));(base/'exact-delivery-identities.json').write_text(json.dumps(dict(runs=exact,scope='Authoritative diagnostics by exact device/epoch/sequence identities, not passive device attribution or predictor input',exit_code=0),indent=2))
 def memory(value):
  v=value.split('/')[0].strip();match=re.fullmatch(r'([0-9.]+)([A-Za-z]+)',v)
  if not match:raise ValueError('Missing Docker memory sample; never zero-fill')
  number=float(match.group(1));unit=match.group(2);return number*dict(B=1,kB=1000,MB=1e6,GB=1e9,KiB=1024,MiB=1024**2,GiB=1024**3)[unit]
 for r in runs:
  w=lookup[r['experiment_id']];duration=w['end']-w['start'];cap=r['capture'];shadow=r['shadow'];selected=[sample for sample in r['resources'] if w['start']<=sample['at']<=w['end']];cpus={};rams={}
  for sample in selected:
   for s in sample['containers']:
    name=s.get('Name','');role='shadow-model' if name.endswith('-worker') else 'shadow-capture' if name.endswith('-capture') else 'receiver' if name.endswith('-receiver-1') else 'postgres' if name.endswith('-postgres-1') else 'other';cpus.setdefault(role,[]).append(float(s['CPUPerc'].strip('%')));rams.setdefault(role,[]).append(memory(s['MemUsage']))
  row=dict(run=r['experiment_id'],devices=r['device_identities'],condition=r['condition'],target_hz=r['target_hz'],active_seconds=duration,formed=r['counters']['formed_aead_packets'],queued=r['counters']['queued'],puback=r['counters']['puback'],pg_committed=r['pg_accepted_delta'],mongo_stored=r['mongo_stored_delta'],accepted_per_second=r['pg_accepted_delta']/duration,captured=cap['stats']['captured'] if cap else None,kernel_drops=cap['stats']['dropped_by_kernel'] if cap else None,reader_drops=cap['reader_drops'] if cap else None,queue_overflow=cap['queue_overflow'] if cap else None,scored=shadow.get('inference_statuses',{}).get('SCORED') if cap else None,unsupported=cap['unsupported'] if cap else None,pending_final=shadow.get('pending'),capture_complete=cap['complete'] if cap else None,outbox_pending_after=r['outbox_pending_after'],resource_sample_count=len(selected))
  for key in ['capture_to_feature','capture_to_prediction','model_batch_wall','capture_to_journal_ack']:
   v=r['timings_seconds'].get(key,{})
   for stat in ['median','mean','p95','p99']:row[key+'_'+stat]=v.get(stat)
  for role in ['shadow-model','shadow-capture','receiver','postgres']:
   row[role+'_cpu_mean']=float(np.mean(cpus[role])) if role in cpus else None;row[role+'_sampled_memory_peak_bytes']=float(max(rams[role])) if role in rams else None
  assert exact[r['experiment_id']]['pg_committed']==r['pg_accepted_delta'] and exact[r['experiment_id']]['mongo_stored']==r['mongo_stored_delta'],'Cohort identity/count mismatch'
  if cap:
   db=Journal(path_for(l.root/'shadow'/r['experiment_id']),readonly=True);status=db.snapshot()['worker'];db.close();row['worker_storage_retries']=status.get('storage_retries');row['worker_storage_commits']=status.get('storage_commits');row['worker_peak_rss_kib']=status.get('peak_rss_kib')
  rows.append(row)
 frame=pd.DataFrame(rows);frame.to_csv(base/'run-summary.csv',index=False);summary=frame.groupby(['devices','condition'],dropna=False).agg(runs=('run','size'),incoming_mean=('accepted_per_second','mean'),incoming_std=('accepted_per_second','std'),latency_median_mean=('capture_to_prediction_median','mean'),latency_median_std=('capture_to_prediction_median','std')).reset_index();summary.to_csv(base/'repeat-summary.csv',index=False)
 report=dict(source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),runs=rows,grouped=summary.replace({np.nan:None}).to_dict('records'),counts=dict(formed=int(frame.formed.sum()),queued=int(frame.queued.sum()),puback=int(frame.puback.sum()),pg_committed=int(frame.pg_committed.sum()),mongo_stored=int(frame.mongo_stored.sum()),captured=int(frame.captured.sum()),scored=int(frame.scored.sum())),limitations=['Three conditional same-host repeats, not independent hardware domains','No causal confidence intervals; varied seeds/startup/TLS/counter shapes','Resource samples cropped to actual traffic window; None never replaced with zero','Short15sec workloads do not prove steady-state maximum capacity','No new generalization holdout or model fitting'],exit_code=0);(base/'performance-summary.json').write_text(json.dumps(report,indent=2,allow_nan=False))
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 out=base/'figures';out.mkdir(exist_ok=True)
 for column,label,name in [('accepted_per_second','PG committed / active second','admission_throughput'),('capture_to_prediction_median','Capture to prediction median, seconds','prediction_latency'),('shadow-model_cpu_mean','Model CPU%, active samples','model_cpu'),('shadow-capture_cpu_mean','Capture CPU%, active samples','capture_cpu'),('shadow-model_sampled_memory_peak_bytes','Docker sampled model memory peak, bytes','model_ram'),('receiver_cpu_mean','Receiver CPU%, active samples','receiver_cpu'),('queue_overflow','Explicit application overflow','capture_overflow')]:
  fig,ax=plt.subplots(figsize=(7,4))
  for condition,part in frame.groupby('condition'):
   values=part.dropna(subset=[column]);g=values.groupby('devices')[column].agg(['mean','std']);
   if len(g):ax.errorbar(g.index,g['mean'],yerr=g['std'],marker='o',linestyle='none',label=condition)
  ax.set_xlabel('Software identities');ax.set_ylabel(label);ax.legend();ax.set_title('Actual Stage15 v3 runs; bars=run SD, not confidence intervals');fig.tight_layout();fig.savefig(out/(name+'.png'),dpi=160);fig.savefig(out/(name+'.svg'));plt.close(fig)
 print('48 real repeated runs summarized; no inference/fit/retuning; exit0')
if __name__=='__main__':main()

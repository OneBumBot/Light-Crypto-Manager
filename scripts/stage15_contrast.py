"""Real same-host operational contrast with independent oracle, never model selection."""
import argparse,json,os,shutil,subprocess,time
from pathlib import Path
import pandas as pd
from scripts.stage15_setup import lab
from scripts.stage15_runs import capture,wait
from scripts.stage15_performance import start_worker
from src.research_stand.orchestrator import Lab as ResearchLab
from src.research_stand.config import Experiment
from src.research_stand.dataset_v2 import build
from src.shadow_ids.journal import Journal,path_for
from src.shadow_ids.models import frozen

def main():
 p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,default=Path('.local-runtime/stage15/online'));a=p.parse_args();l=lab(a.directory);output=Path('docs/reports/stage15/operational-contrast.json')
 if output.exists():raise ValueError('Immutable contrast report')
 sources=l.root/'corroboration';sources.mkdir(mode=0o700,exist_ok=True);research=ResearchLab(l.env,sources,compose_overrides=[l.root/'stage15.compose.json',Path('compose.shadow.yaml')]);records=[]
 scenarios=['regular','jitter','qos1_retry','replay','wrong_epoch','wrong_sequence','tampered','forbidden_acl','bad_credentials','bounded_rate','pattern_change','broker_reconnect','receiver_restart'];pins=frozen()
 for i,kind in enumerate(scenarios):
  name='online-'+kind.replace('_','-');root=l.root/'shadow'/name;cid=capture(l,name,condition='all',duration=38);wid=start_worker(l,name,['rf_binary','if','rf_session','if_session']);status='complete';error=None;old=research.resource_usage;calls=[0]
  def usage():
   value=old();calls[0]+=1
   if calls[0]==2 and kind in ['broker_reconnect','receiver_restart']:l.run('restart','broker' if kind=='broker_reconnect' else 'receiver')
   return value
  research.resource_usage=usage
  try:research.experiment(Experiment(name,kind if kind not in ['broker_reconnect','receiver_restart'] else 'regular',3,6,.5,.02,15500+i,kind in ['replay','wrong_epoch','wrong_sequence','tampered','forbidden_acl','bad_credentials','bounded_rate','pattern_change']))
  except Exception as exc:status='quarantined';error=type(exc).__name__
  finally:research.resource_usage=old
  wait(cid);wait(wid);cap=json.loads((root/'capture-status.json').read_text());labels=None;metrics={};reason=None
  if status=='complete' and cap['complete']:
   # Reannotate the *actual Shadow PCAP*. Ground truth sources are independent of
   # predictions; no packet-count matching or new physical capture is invented.
   view=l.root/'label-views'/name;folder=view/name;folder.mkdir(parents=True,mode=0o700)
   for fn in ['ground-truth.json','broker-events.json','broker-evidence.json','mqtt-observer.json','core.json']:shutil.copyfile(sources/name/fn,folder/fn)
   shutil.copyfile(root/'traffic.pcap',folder/'traffic.pcap');meta=dict(schema_version=1,pcap_sha256=cap['pcap_sha256'],started_at=cap['started_at'],finished_at=cap['finished_at'],stats=cap['stats'],stop_reason='duration');(folder/'capture.json').write_text(json.dumps(meta))
   l.run('run','--rm','--no-deps','--user',str(os.getuid())+':'+str(os.getgid()),'-v',str(folder)+':/parity','traffic-collector','python','-m','src.research_stand.collector','extract','--directory','/parity')
   try:
    dataset=view/'dataset';build(view,dataset);frame=pd.read_csv(dataset/'observations.csv',keep_default_na=False);labels={str(k):int(v) for k,v in frame.ground_truth.value_counts().items()};by_number={int(r['packet_id'].rsplit(':',1)[1]):r for r in frame.to_dict('records')};db=Journal(path_for(root),readonly=True);predictions=[json.loads(r[0]) for r in db.db.execute('SELECT value FROM results')];db.close()
    for role in ['rf_binary','if','rf_session','if_session']:
     scored=[r for r in predictions if r['model_role']==role and r['inference_status']=='SCORED'];normal=[r for r in scored if by_number[r['packet_identity']['ordinal']]['ground_truth']=='normal'];cv=[r for r in scored if by_number[r['packet_identity']['ordinal']]['ground_truth']=='controlled_violation'];fp=sum(r['comparison'] for r in normal);cross=sum(r['comparison'] for r in cv);session_rows={}
     for r in scored:
      label=by_number[r['packet_identity']['ordinal']]
      if label['ground_truth']!='normal':continue
      session_rows.setdefault(label['session_id'],[]).append(r)
     method=pins[role]['session']['method'];threshold=pins[role]['session']['point']['threshold'];session_alerts=0
     for rows in session_rows.values():
      score=sum(r['score'] for r in rows)/len(rows) if method=='mean' else max(r['score'] for r in rows) if method=='max' else sum(r['comparison'] for r in rows)/len(rows);session_alerts+=int(score>=threshold)
     metrics[role]=dict(normal_scored_observations=len(normal),false_positive_observations=int(fp),packet_fpr=fp/len(normal) if normal else None,known_normal_activity_sessions=len(session_rows),normal_activity_session_false_alarms=session_alerts,false_alarms_per_known_normal_activity_session=session_alerts/len(session_rows) if session_rows else None,cv_scored_observations=len(cv),cv_threshold_crossings=int(cross),unknown_scored_observations=len(scored)-len(normal)-len(cv),scope='Oracle-confirmed activity windows only; session aggregation here over known-normal subset, separate from full causal online session prefix',false_alarm_events_per_nominal_run_hour=fp/(json.loads((sources/name/'ground-truth.json').read_text())['experiment_finished_at']-json.loads((sources/name/'ground-truth.json').read_text())['experiment_started_at'])*3600 if normal and kind in ['regular','jitter','qos1_retry'] else None,rate_unit='Repeated packet threshold events per actual lab-run wall duration scaled to hour, not latched incident alerts/hour')
   except (ValueError,KeyError,TypeError) as exc:reason=type(exc).__name__;status='LABEL_ORACLE_BLOCKED'
  else:reason='Independent source or Shadow context incomplete; FPR not_evaluable'
  record=dict(case=kind,status=status,diagnostic=error,labels=labels,metrics=metrics,label_failure=reason,capture_complete=cap['complete'],capture_drops=cap['stats'],independent_host_domain='not_verified',generalization_evaluation='BLOCKED_INDEPENDENT_DATA',device_binding='unbound',fit_or_threshold_changes=0,source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip());records.append(record);(output.with_name('operational-contrast-progress.json')).write_text(json.dumps(dict(records=records),indent=2));print(kind,status,labels,flush=True)
 output.write_text(json.dumps(dict(cases=records,scope='Same-host operational contrast, not new independent generalization holdout',old_holdout_reused=False,fit_calls=0,threshold_changes=0,exit_code=0),indent=2))
if __name__=='__main__':main()

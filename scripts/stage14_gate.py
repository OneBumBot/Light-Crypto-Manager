"""Independent source validation -> linked frozen split -> explicit offline permission."""
import argparse,json,os,subprocess
from pathlib import Path
import pandas as pd
from src.research_stand.stage14 import checked_collection_plan,verify_source_receipt,linked_split
from src.research_stand.dataset_v2 import build
from src.research_stand.label_verification import reconcile
from src.research_stand.pcap_audit import digest,load_json


def main():
 p=argparse.ArgumentParser();p.add_argument('--captures',type=Path,default=Path('.local-runtime/stage14/primary-captures'));p.add_argument('--dataset',type=Path,default=Path('.local-runtime/stage14/lightcrypto-lab-v1'));p.add_argument('--plan',type=Path,default=Path('docs/reports/stage14/collection-plan.json'));p.add_argument('--report',type=Path,default=Path('docs/reports/stage14/data-quality-gate.json'));a=p.parse_args()
 if a.report.exists() or a.dataset.exists():p.error('Immutable gate/dataset output')
 os.umask(0o077);plan=checked_collection_plan(a.plan);checks={k:False for k in ['raw_sources','label_oracle','source_novelty','independence','feature_schema','strict_split','frozen_holdout','no_resource_truncation']};reason=None;status='BLOCKED_BY_LABEL_ORACLE';manifest=None;split=None;staging=a.dataset.with_name(a.dataset.name+'-building')
 try:
  expected={r['config']['experiment_id']:r for r in plan['primary']}
  if not a.captures.exists() or {f.name for f in a.captures.iterdir() if f.is_dir()}!=set(expected):raise ValueError('Missing/unexpected primary acquisition captures')
  receipts=[verify_source_receipt(a.captures/name,plan) for name in sorted(expected)]
  checks['raw_sources']=True;checks['no_resource_truncation']=True
  hashes=[r['pcap_sha256'] for r in receipts]
  historical=load_json('docs/reports/stage14/preservation-before.json')['snapshot']['private_files'];old_pcaps={v for k,v in historical.items() if k.endswith(('.pcap','.pcapng'))}
  if len(hashes)!=len(set(hashes)) or set(hashes)&old_pcaps:status='BLOCKED_BY_INDEPENDENCE';raise ValueError('Copied physical capture/source novelty failure')
  checks['source_novelty']=True
  # Pair dependence is forced by broker/device authority; shared seeds across groups are forbidden.
  realms={};seeds={}
  for r in receipts:
   for key,table in [(r['project'],realms),(r['config']['seed'],seeds)]:
    if key in table and table[key]!=r['group']:status='BLOCKED_BY_INDEPENDENCE';raise ValueError('Unmerged cross-group acquisition dependence')
    table[key]=r['group']
  checks['independence']=True
  build(a.captures,staging)
  observations=pd.read_csv(staging/'observations.csv',dtype=str,keep_default_na=False)
  mapping={r['config']['experiment_id']:r for r in plan['primary']}
  observations['independence_group']=observations.experiment_id.map(lambda v:mapping[v]['group']);observations['broker_realm']=observations.experiment_id.map(lambda v:mapping[v]['project']);observations['preregistered_partition']=observations.experiment_id.map(lambda v:mapping[v]['partition'])
  observations.to_csv(staging/'observations.csv',index=False);observations.loc[observations.ground_truth!='unknown'].to_csv(staging/'dataset.csv',index=False)
  manifest=load_json(staging/'dataset.manifest.json');manifest.update(dataset_version='stage14-lightcrypto-lab-v1',collection_plan_sha256=plan['sha256'],stage14_group_partitions={r['group']:r['partition'] for r in plan['primary']},columns=list(observations),sha256=digest(staging/'dataset.csv'),observations_sha256=digest(staging/'observations.csv'))
  if manifest['synthetic']:raise ValueError('Synthetic data cannot pass Stage14 real capture gate')
  (staging/'dataset.manifest.json').write_text(json.dumps(manifest,indent=2));reconciliation=reconcile(staging,a.captures);checks['label_oracle']=True;checks['feature_schema']=True
  (staging/'reconciliation.json').write_text(json.dumps(reconciliation,indent=2))
  frame=pd.read_csv(staging/'dataset.csv')
  counts={str(k):int(v) for k,v in observations.ground_truth.value_counts().items()}
  by_scenario={}
  for scenario,rows in observations.groupby('scenario_category'):
   known=rows.loc[rows.ground_truth!='unknown'];conn=rows.groupby('connection_id').ground_truth.agg(lambda x:set(x)-{'unknown'})
   by_scenario[scenario]=dict(captures=int(rows.capture_id.nunique()),observations=len(rows),labels={str(k):int(v) for k,v in rows.ground_truth.value_counts().items()},normal_connections=sum(v=={'normal'} for v in conn),controlled_violation_connections=sum(v=={'controlled_violation'} for v in conn),connections_without_known_rows=sum(not v for v in conn),partition_class_support={part:{label:int(rows.loc[(rows.preregistered_partition==part)&(rows.ground_truth==label),'capture_id'].nunique()) for label in ['normal','controlled_violation']} for part in ['train','validation','test']})
  validation=dict(observations=len(observations),known_rows=len(frame),unknown_rows=counts.get('unknown',0),unknown_fraction=counts.get('unknown',0)/len(observations),class_counts=counts,per_scenario=by_scenario,corroborated_connections=reconciliation['corroborated_connections'],label_unit='connection_activity/window_behavior, not per-packet attack',holdout_access='structural support counts only; no model scoring',external_domain_validation='not_performed')
  (staging/'validation.json').write_text(json.dumps(validation,indent=2));(a.report.parent/'coverage.json').write_text(json.dumps(validation,indent=2))
  try:
   split=linked_split(frame,manifest['stage14_group_partitions']);checks['strict_split']=True;checks['frozen_holdout']=True;status='PASS'
   (staging/'split.json').write_text(json.dumps(split,indent=2))
  except ValueError as e:status='BLOCKED_BY_DATA_QUALITY';reason=str(e);(staging/'split-attempt.json').write_text(json.dumps(dict(status=status,reason=reason,assignments=manifest['stage14_group_partitions'],minimum_normal_rows=1000,minimum_class_groups=5),indent=2))
 except (ValueError,KeyError,TypeError,FileNotFoundError,RuntimeError) as e:
  reason=reason or type(e).__name__+':'+str(e)
  if 'resource' in str(e).lower() or 'bound100000' in str(e):status='BLOCKED_BY_RESOURCE_LIMIT'
 a.report.parent.mkdir(parents=True,exist_ok=True)
 report=dict(schema_version=1,status=status,checks=checks,reason=reason,source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),collection_plan=str(a.plan.resolve()),collection_plan_sha256=plan['sha256'],raw_capture_root=str(a.captures.resolve()),dataset_sha256=manifest['sha256'] if manifest else None,manifest_sha256=digest(staging/'dataset.manifest.json') if manifest else None,split_sha256=split['sha256'] if split else None,training_permission='OFFLINE_RESEARCH_ONLY' if status=='PASS' else 'NOT_EXECUTED_DATA_QUALITY_GATE',trusted_detector=False,policy_mode='DRY_RUN',external_domain_validation='not_performed',exit_code=0 if status=='PASS' else 2)
 if staging.exists():
  (staging/'data-quality-gate.json').write_text(json.dumps(report,indent=2));staging.rename(a.dataset)
 a.report.write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2));raise SystemExit(report['exit_code'])
if __name__=='__main__':main()

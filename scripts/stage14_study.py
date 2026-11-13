"""Bounded offline training and one frozen holdout battery; no model installation."""
import argparse,hashlib,json,os,resource,subprocess
from pathlib import Path

METHOD_FILES=['src/classifier/research/experiment.py','src/classifier/research/schema.py','src/classifier/research/metrics.py','src/classifier/research/group_metrics.py']


def method_hashes():return {p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in METHOD_FILES}


def main():
 p=argparse.ArgumentParser();p.add_argument('action',choices=['train','test']);p.add_argument('--dataset',type=Path,default=Path('.local-runtime/stage14/lightcrypto-lab-v1'));p.add_argument('--root',type=Path,default=Path('.local-runtime/stage14/study'));p.add_argument('--reports',type=Path,default=Path('docs/reports/stage14'));a=p.parse_args();os.umask(0o077)
 resource.setrlimit(resource.RLIMIT_CPU,(900,900));resource.setrlimit(resource.RLIMIT_AS,(3*2**30,3*2**30));resource.setrlimit(resource.RLIMIT_FSIZE,(2**30,2**30))
 from src.classifier.research import experiment as ex
 from src.classifier.ml.artifacts import load,file_hash
 from src.classifier.research.datasets import canonical_hash
 from src.research_stand.stage14 import training_gate
 from src.research_stand.pcap_audit import load_json
 data=a.dataset/'dataset.csv';manifest=a.dataset/'dataset.manifest.json';training_gate(data,manifest);config=load_json(a.reports/'training-config.json');gate=load_json(a.dataset/'data-quality-gate.json');study_plan=a.root/'plan.json';models=a.root/'models';experiment=a.root/'experiment';method=a.root/'method-freeze.json'
 if a.action=='train':
  if a.root.exists():raise ValueError('Existing study/artifacts preserved; no automatic retry/reset')
  a.root.mkdir(parents=True,mode=0o700);snapshot=dict(source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),code_hashes=method_hashes(),config_sha256=canonical_hash(config),data_gate_sha256=file_hash(a.dataset/'data-quality-gate.json'),stage14_only=True,threads=1,cpu_seconds=900,address_space_bytes=3*2**30)
  method.write_text(json.dumps(snapshot,indent=2));planned=ex.plan(data,manifest,config,study_plan);assert planned['split']['sha256']==gate['split_sha256']
  frozen=ex.train(data,manifest,study_plan,models,experiment);assert len(frozen['models'])==23 and all(not r['multiclass'] for r in frozen['models']);(a.reports/'train-freeze.json').write_text(json.dumps(frozen,indent=2));(a.reports/'study-plan-summary.json').write_text(json.dumps(dict(plan_sha256=planned['plan_sha256'],split_sha256=planned['split']['sha256'],summary=planned['split']['summary'],method=snapshot,fit_completed=True,holdout_evaluated=False,exit_code=0),indent=2));print('All23 preregistered fits and validation-only calibration frozen; holdout not evaluated; exit0');return
 snapshot=load_json(method)
 if snapshot['code_hashes']!=method_hashes() or snapshot['config_sha256']!=canonical_hash(config) or snapshot['data_gate_sha256']!=file_hash(a.dataset/'data-quality-gate.json'):raise ValueError('Frozen evaluation method/config/data gate changed')
 frame,source,planned=ex.checked_plan(data,manifest,study_plan);freeze=load_json(experiment/'freeze.json');given=freeze.pop('sha256');assert canonical_hash(freeze)==given
 assert not (experiment/'final-test-started').exists() and len(freeze['models'])==23
 records=[]
 for row in freeze['models']:
  meta,pipeline=load(models,row['model_id'],row['model_version']);assert meta['artifact_sha256']==row['artifact_sha256'] and meta['threshold']==row['threshold']['threshold'] and meta['trusted_detector'] is False and meta['mode']=='RESEARCH'
  assert row['session_calibration']['selected']['method'] in ['mean','max','fraction']
  if row['algorithm']=='if':assert row['timing']['fit_attack']==0
  else:assert row['timing']['fit_rows']==len(planned['split']['indices'][0])
  records.append(dict(model_id=row['model_id'],artifact_sha256=row['artifact_sha256'],packet_threshold=meta['threshold'],session_threshold=row['session_calibration']['selected']['point']['threshold'],trusted_detector=False))
 audit=dict(method=snapshot,freeze_sha256=given,plan_sha256=planned['plan_sha256'],records=records,no_holdout_prediction_before_marker=True,exit_code=0);(a.reports/'pre-test-audit.json').write_text(json.dumps(audit,indent=2))
 result=ex.final_test(data,manifest,study_plan,models,experiment)
 # Publish metrics/hash references only; raw capture/data/model artifacts remain private.
 public=dict(scope=result['scope'],source_sha=snapshot['source_sha'],dataset_sha256=source['sha256'],split_sha256=planned['split']['sha256'],split_summary=planned['split']['summary'],freeze_sha256=given,versions=result['versions'],results=result['results'],external_domain_validation='not_performed',trusted_detector=False,policy_mode='DRY_RUN',final_test_calls=1,exit_code=0)
 (a.reports/'rf-if-results.json').write_text(json.dumps(public,indent=2));print('Once-only frozen23-model holdout battery completed; no retuning; exit0')
if __name__=='__main__':main()

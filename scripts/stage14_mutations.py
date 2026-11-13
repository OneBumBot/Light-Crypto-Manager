"""Behavioral source mutations in disposable copies; no raw collection/model fitting."""
import argparse,json,os,shutil,subprocess,tempfile
from pathlib import Path


def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():p.error('Immutable report')
 root=Path.cwd();python=str(root/'.venv/bin/python');cases=[]
 def add(name,file,before,after,test):cases.append(dict(name=name,edits=[(file,before,after)],test=test))
 lab='src/research_stand/labels_v2.py';oracle='src/research_stand/label_verification.py';ex='src/classifier/research/experiment.py';stage='src/research_stand/stage14.py';collect='scripts/stage14_collect.py'
 add('unknown_to_normal',lab,'        label = "unknown"','        label = "normal"','test_ground_truth_hardening.py::test_no_syn_pipeline_cannot_attribute')
 add('unknown_to_violation',lab,'        label = "unknown"','        label = "controlled_violation"','test_ground_truth_hardening.py::test_no_syn_pipeline_cannot_attribute')
 add('scenario_replaces_broker_outcome',lab,'s["auth_code"] == 5 and record.get("auth_rejected")','record.get("auth_rejected")','test_ground_truth_hardening.py::test_generator_flag_cannot_replace_broker_result')
 add('wrong_tcp_session',lab,'assigned[key] = matches[0]','assigned[key] = truth["connections"][0]','test_ground_truth_hardening.py::test_public_pipeline_positive_mixed_and_unknown')
 add('physical_pcap_digest_ignored','src/research_stand/pcap_audit.py','digest(folder / "traffic.pcap") != cap["pcap_sha256"]','False','test_stage14.py::test_coherent_source_metadata_cannot_replace_physical_pcap_digest')
 add('missing_broker_promoted',lab,'return "unknown", "independent_session_evidence_missing", "", lo, hi','return "normal", REASONS["normal"], record["logical_device"], lo, hi','test_ground_truth_hardening.py::test_absent_broker_source_makes_every_connection_unknown')
 add('missing_witness_ignored',lab,'and digest_proof','and True','test_stage14.py::test_replay_requires_independent_timed_identity_and_qos1_is_normal[missing_digest]')
 add('wrong_pg_binding_ignored',lab,'bool(prior and repeated and prep and pubs)','bool(prep and pubs)','test_stage14.py::test_replay_requires_independent_timed_identity_and_qos1_is_normal[wrong_epoch]')
 cases.append(dict(name='duplicate_physical_capture_under_new_filename',edits=[('src/research_stand/dataset_v2.py','if cap["pcap_sha256"] in seen_pcap:','if False:'),(oracle,'if cap["pcap_sha256"] in seen_pcap:','if False:')],test='test_ground_truth_hardening.py::test_copied_pcap_cannot_inflate_independent_capture_support'))
 add('independence_from_filename_only',stage,"'capture_id','session_id','source_pcap_sha256','independence_group'","'capture_id','session_id','independence_group'",'test_stage14.py::test_shared_lineage_cannot_hide_behind_new_capture_name[source_pcap_sha256]')
 add('overlap_in_coherently_rehashed_split',ex,"if actual!=p['split']:","if False:",'test_stage14.py::test_coherently_modified_partition_still_rejected')
 add('preprocessing_fit_on_full_data',ex,'sub=frame.iloc[indices]','sub=frame','test_research75.py::test_schema_nonfinite_types_and_missing_imputed_on_train_only')
 add('holdout_labels_enter_fit',ex,'sub=frame.iloc[indices]','sub=frame.iloc[list(range(len(frame)//2,len(frame)))+list(indices)]','test_research75.py::test_balancing_is_train_only_and_provenance_cannot_be_predictive')
 add('threshold_selected_on_holdout',ex,"validation=frame.iloc[val_idx]","validation=frame.iloc[p['split']['indices'][2]]",'test_stage14.py::test_validation_selection_cannot_read_holdout')
 add('repeat_final_test_allowed',ex,'os.O_WRONLY|os.O_CREAT|os.O_EXCL','os.O_WRONLY|os.O_CREAT','test_research75.py::test_freeze_artifacts_once_only_test_and_offline_inference')
 add('oversampling_before_split',ex,'split=source_split(frame,source,config)','frame=frame.loc[frame.index.repeat(2)].reset_index(drop=True);split=source_split(frame,source,config)','test_stage14.py::test_no_oversampling_or_fit_before_group_split')
 cases.append(dict(name='frozen_configuration_integrity_checks_disabled',edits=[(ex,"if canonical_hash(p)!=digest:","if False:"),(ex,"if canonical_hash(p['config'])!=p['config_sha256']:","if False:"),(ex,"if actual!=p['split']:","if False:")],test='test_stage14.py::test_changed_frozen_configuration_cannot_reach_fit'))
 add('unknown_rows_removed_from_audit','src/research_stand/dataset_v2.py','frame = pd.DataFrame(data)','frame = pd.DataFrame(data); frame=frame.loc[frame.ground_truth!="unknown"]','test_ground_truth_hardening.py::test_public_pipeline_positive_mixed_and_unknown')
 add('qos1_dup_called_attack',lab,'        retry = any(e.get("dup") == 1 for e in pubs) and any(e["category"] == "replay" for e in pg)','        retry = any(e.get("dup") == 1 for e in pubs) and any(e["category"] == "replay" for e in pg)\n        if retry:return "controlled_violation", "DUP_ATTACK", device_binding, lo, hi','test_stage14.py::test_replay_requires_independent_timed_identity_and_qos1_is_normal[qos1_normal]')
 add('connection_label_called_packet_specific',lab,'label_unit="connection_activity"','label_unit="packet_attack"','test_ground_truth_hardening.py::test_public_pipeline_positive_mixed_and_unknown')
 add('empty_positive_class_perfect_recall','src/classifier/research/metrics.py','float(r[1]) if positive.any() else None','float(r[1]) if positive.any() else 1.0','test_research75.py::test_operating_point_empty_class_scores_and_group_uncertainty')
 add('offline_ml_becomes_trusted','src/classifier/research/inference.py','trusted_detector=False','trusted_detector=True','test_stage14.py::test_offline_risk_is_untrusted_unattributed_and_cannot_request_control')
 add('offline_rf_requests_crypto_control','src/classifier/research/inference.py','    scores=risk(pipeline,frame,algorithm)',"    from src.device_control.server import request_switch\n    request_switch(None,'lab001','aes-128-gcm-v1','RF')\n    scores=risk(pipeline,frame,algorithm)",'test_stage14.py::test_offline_risk_is_untrusted_unattributed_and_cannot_request_control')
 add('observer_loss_not_quarantined',collect," or not observer.get('completed')",'', 'test_stage14.py::test_source_loss_and_partial_data_cannot_be_complete[observer_lost]')
 add('partial_capture_called_complete',collect," if cap['started_at']>truth['experiment_started_at'] or cap['finished_at']<truth['experiment_finished_at']:raise ValueError('Partial capture does not cover generator lifecycle')",'', 'test_stage14.py::test_source_loss_and_partial_data_cannot_be_complete[partial_capture]')
 add('early_generator_called_complete',collect," if truth['experiment_finished_at']-truth['experiment_started_at']<truth['experiment']['duration']-.05:raise ValueError('Generator stopped before planned duration')",'', 'test_stage14.py::test_source_loss_and_partial_data_cannot_be_complete[early_generator]')
 pre=subprocess.run([python,'-m','pytest','-q','--noconftest','tests/test_stage14.py','tests/test_ground_truth_hardening.py','tests/test_research75.py'],capture_output=True,text=True,timeout=90)
 if pre.returncode:raise RuntimeError('Unmutated baseline failed:'+pre.stdout[-1500:]+pre.stderr[-200:])
 results=[]
 for case in cases:
  with tempfile.TemporaryDirectory(prefix='lcm-stage14-mutation-') as temporary:
   dest=Path(temporary);shutil.copytree(root/'src',dest/'src',ignore=shutil.ignore_patterns('__pycache__','Edge-IIoTset dataset','*.ipynb','*.zip'));(dest/'tests').mkdir();(dest/'scripts').mkdir()
   for name in ['test_stage14.py','test_ground_truth_hardening.py','test_research75.py']:shutil.copyfile(root/'tests'/name,dest/'tests'/name)
   for name in ['stage14_collect.py','stage14_lab.py']:shutil.copyfile(root/'scripts'/name,dest/'scripts'/name)
   for file,before,after in case['edits']:
    path=dest/file;text=path.read_text()
    if before not in text:raise ValueError('Stale selector: '+case['name'])
    path.write_text(text.replace(before,after,1))
   r=subprocess.run([python,'-m','pytest','-q','--noconftest','tests/'+case['test']],cwd=dest,env=dict(os.environ,PYTHONPATH=str(dest),PYTHONDONTWRITEBYTECODE='1'),capture_output=True,text=True,timeout=90);output=r.stdout+r.stderr
   killed=r.returncode==1 and 'FAILED' in output and not any(x in output for x in ['SyntaxError','ImportError','ModuleNotFoundError','ERROR collecting'])
   results.append(dict(defect=case['name'],test=case['test'],edits=case['edits'],exit_code=r.returncode,killed_by_behavior=killed,output_tail=output[-2500:]));print(case['name'],killed,flush=True)
 report=dict(source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),baseline_exit_code=pre.returncode,baseline_output=pre.stdout,results=results,all_killed=all(r['killed_by_behavior'] for r in results),scope='Disposable source copies and synthetic program fixtures; no scientific RF/IF fit or real-capture metrics',exit_code=0 if all(r['killed_by_behavior'] for r in results) else 1);a.output.write_text(json.dumps(report,indent=2));raise SystemExit(report['exit_code'])
if __name__=='__main__':main()

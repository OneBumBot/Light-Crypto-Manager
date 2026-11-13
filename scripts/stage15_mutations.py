"""Disposable program mutations only; never loads data/models or changes active sources."""
import argparse,json,os,shutil,subprocess,tempfile
from pathlib import Path

def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():p.error('Immutable output')
 root=Path.cwd();python=str(root/'.venv/bin/python');cases=[]
 f='src/shadow_ids/features.py';m='src/shadow_ids/models.py';w='src/shadow_ids/worker.py';j='src/shadow_ids/journal.py'
 def add(name,edits,test):cases.append(dict(name=name,edits=edits,test=test))
 add('missing_timestamp_zero',[(f," if type(timestamp) not in", " if timestamp is None:timestamp=0\n if type(timestamp) not in")],'test_timestamp_unavailable[None]')
 add('negative_delta_clamped',[(f,"delta=t-r['last']","delta=max(0,t-r['last'])")],'test_negative_delta_is_not_clamped')
 add('streams_share_context',[(f,"key=p['key'];syn=", "key=(('all',0),('all',0));syn=")],'test_two_streams_not_shared')
 add('tuple_reuse_not_reset',[(f," or (syn and (old['closed'] or old['initial']!=p['sequence']))",'')],'test_reused_tuple_resets_generation')
 add('missing_syn_complete',[(f,"complete=syn,diagnostic=","complete=True,diagnostic="),(f,"if not p['flags']&2:r['complete']=False","if False:r['complete']=False")],'test_missing_syn_insufficient[16]')
 add('packet_loss_ignored',[(f,"for r in self.rows.values():r['complete']=False","for r in self.rows.values():r['complete']=True")],'test_gap_requires_new_generation')
 add('truncated_frame_accepted',[(f," or len(raw)!=original",''),(f,' or n>len(ip)','')],'test_unsupported_not_scored[truncated]')
 add('feature_order_ignored',[(m," or list(features)!=list(FEATURES)",'')],'test_features_missing_metadata_order_and_version_rejected')
 add('feature_version_ignored',[(m,"event.get('feature_version')!=VERSION or ",'')],'test_features_missing_metadata_order_and_version_rejected')
 before="if hashlib.sha256((path/'manifest.json').read_bytes()).hexdigest()!=pin['manifest_sha256'] or meta['artifact_sha256']!=pin['artifact_sha256'] or meta['threshold']!=pin['threshold'] or meta['feature_version']!=VERSION or meta.get('mode')!='RESEARCH' or meta.get('trusted_detector') is not False or meta.get('preprocessing',{}).get('feature_order')!=list(FEATURES):"
 add('unapproved_artifact_deserialized',[(m,before,'if False:')],'test_frozen_model_hash_version_threshold_before_deserialization')
 add('threshold_changed_after_freeze',[(w,"threshold=pin['threshold'],comparison=","threshold=pin['threshold']+.1,comparison=")],'test_scored_threshold_is_original_and_unbound')
 add('network_metadata_predictor',[(m,'out={}\n for role',"frame['device_id']='broker';out={}\n for role")],'test_network_metadata_never_enters_predictors')
 add('invalid_score_becomes_normal',[(m,'or not np.isfinite(values).all()', ''),(m,'out[role]=[float(x) for x in values]','out[role]=[float(np.nan_to_num(x)) for x in values]')],'test_nonfinite_score_is_error_without_plain_normal')
 add('no_model_score_zero',[(w,"status=event['status'];score=None","status=event['status'];score=0.0")],'test_no_model_is_unavailable_not_normal')
 add('broker_identity_authenticated',[(w,"device_binding='unbound',mode='SHADOW_ONLY'","device_binding='broker',mode='SHADOW_ONLY'"),(j," or result.get('device_binding')!='unbound'",'')],'test_scored_threshold_is_original_and_unbound')
 add('rejected_connection_device_identity',[(w,"device_binding='unbound',mode='SHADOW_ONLY'","device_binding=event.get('device_id','unbound'),mode='SHADOW_ONLY'"),(j," or result.get('device_binding')!='unbound'",'')],'test_scored_threshold_is_original_and_unbound')
 add('duplicate_observation_inserted',[(j,'id TEXT PRIMARY KEY,run','id TEXT,run'),(j,',UNIQUE(run,ordinal)',''),(j,"if self.db.execute('SELECT 1 FROM events WHERE id=?',(event['event_id'],)).fetchone():return False","if False:return False")],'test_journal_duplicate_and_atomicity')
 add('worker_receiver_failure_coupling_allowed',[('src/shadow_ids/isolation.py',"if capture.get('network_mode')!='service:lab-devices':","if False:")],'test_deployment_rejects_receiver_coupling')
 add('shadow_writes_policy',[(w,'  pairs.append((row,results))',"  from src.policy.state import process as emit\n  emit(None,None,None,None)\n  pairs.append((row,results))")],'test_no_policy_or_control_side_effects')
 add('shadow_crypto_command',[(w,'  pairs.append((row,results))',"  from src.device_control.server import request_switch\n  request_switch(None,'alpha','aes-128-gcm-v1','RF')\n  pairs.append((row,results))")],'test_no_policy_or_control_side_effects')
 add('broken_capture_healthy',[(j,"  if capture.get('status')=='CAPTURE_INCOMPLETE':current=False",'')],'test_broken_capture_not_healthy_and_stale_evidence_not_fresh')
 add('overflow_hidden',[(j,"  last_packet=capture.get('last_packet');", "  capture.pop('queue_overflow',None)\n  last_packet=capture.get('last_packet');")],'test_stale_clears_predictions_and_overflow_visible')
 add('stale_inference_fresh',[(j," and worker['evidence_fresh']",'')],'test_broken_capture_not_healthy_and_stale_evidence_not_fresh')
 add('old_holdout_reused',[(m,' frame=pd.DataFrame('," from src.classifier.research.experiment import final_test\n final_test(None,None,None,None,None)\n frame=pd.DataFrame(")],'test_no_fit_or_old_holdout_during_shadow_model_scoring')
 add('full_session_backdated',[('src/shadow_ids/sessions.py',"evaluated_at=time.time(),final=final","evaluated_at=v['first_timestamp'],final=final")],'test_session_scores_are_causal_prefixes')
 add('sequence_gap_ignored',[(f,"if 0<distance<2**31:r['complete']=False;r['diagnostic']='tcp_sequence_gap'","if False:r['complete']=False")],'test_transport_sequence_gap_invalidates_context')
 add('batch_state_marker_partial_commit',[(j,"  with self.write():\n   for row,results in pairs:self.complete(row,results)","  for row,results in pairs:self.complete(row,results)")],'test_batch_rollback_preserves_pending_and_no_partial_results')
 add('sqlite_busy_retry_disabled',[(j,'if attempt==5:raise','if attempt==0:raise')],'test_bounded_busy_retry_not_lost_processing')
 add('reordered_syn_falsely_complete',[(f,'new=not regressed and (','new=(')],'test_reordered_syn_not_a_fresh_complete_generation')
 pre=subprocess.run([python,'-m','pytest','-q','--noconftest','tests/test_shadow_ids.py'],capture_output=True,text=True,timeout=90)
 if pre.returncode:raise RuntimeError('Unmutated tests failed:'+pre.stdout[-1500:])
 results=[]
 for case in cases:
  with tempfile.TemporaryDirectory(prefix='lcm-stage15-mutant-') as directory:
   dest=Path(directory);shutil.copytree(root/'src',dest/'src',ignore=shutil.ignore_patterns('__pycache__','Edge-IIoTset dataset','*.zip','*.ipynb'));(dest/'tests').mkdir();shutil.copyfile(root/'tests/test_shadow_ids.py',dest/'tests/test_shadow_ids.py')
   for file,before,after in case['edits']:
    path=dest/file;text=path.read_text()
    if before not in text:raise ValueError('Stale mutation selector: '+case['name'])
    path.write_text(text.replace(before,after,1))
   r=subprocess.run([python,'-m','pytest','-q','--noconftest','tests/test_shadow_ids.py::'+case['test']],cwd=dest,env=dict(os.environ,PYTHONPATH=str(dest),PYTHONDONTWRITEBYTECODE='1'),capture_output=True,text=True,timeout=60);output=r.stdout+r.stderr;killed=r.returncode==1 and 'FAILED' in output and not any(s in output for s in ['SyntaxError','ImportError','ModuleNotFoundError','ERROR collecting']);results.append(dict(defect=case['name'],edits=case['edits'],test=case['test'],exit_code=r.returncode,killed_by_behavior=killed,output_tail=output[-2400:]));print(case['name'],killed,flush=True)
 report=dict(source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),baseline_exit_code=pre.returncode,baseline_output=pre.stdout,results=results,all_killed=all(r['killed_by_behavior'] for r in results),scope='Synthetic program fixtures in disposable copies; not IDS quality evidence',exit_code=0 if all(r['killed_by_behavior'] for r in results) else 1);a.output.write_text(json.dumps(report,indent=2));raise SystemExit(report['exit_code'])
if __name__=='__main__':main()

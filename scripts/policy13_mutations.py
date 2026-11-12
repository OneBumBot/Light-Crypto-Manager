"""Behavioral Policy defects in temporary source/schema copies, never the lab authority."""
import argparse,json,os,subprocess,tempfile,shutil,sys,hashlib
from pathlib import Path

W='src/policy/worker.py';S='src/policy/state.py';E='src/policy/engine.py';D='src/policy/diagnostics.py';M='migrations/versions/0011_policy_throughput.py'
T='test_policy_throughput.py::'
CASES=[]
def add(name,path,old,new,test):CASES.append((name,path,old,new,T+test if not test.startswith('test_policy_engine') else test))
add('late_source_dequeued_without_audit',W,"                bound=row['device_id'] is not None", "                previous=c.scalar(select(states.c.state).where(states.c.device_id==row['device_id'],states.c.version==version))\n                if previous and previous.get('last_event_at') and utc(row['occurred_at'])<utc(previous['last_event_at']):\n                    c.execute(delete(pending).where(pending.c.event_id==item['event_id']));count+=1;continue\n                bound=row['device_id'] is not None",'test_late_insert_is_discovered_and_audited')
add('reverse_device_order',W,'.order_by(pending.c.sort_at,pending.c.event_id)','.order_by(pending.c.sort_at.desc(),pending.c.event_id.desc())','test_parallel_workers_serialize_without_skipping_device_order')
add('state_committed_without_signal',S,'    if before_commit:before_commit()',"    connection.execute(signals.delete().where(signals.c.event_id==signal.event_id,signals.c.version==version))\n    if before_commit:before_commit()",'test_golden_sequential_vs_optimized')
add('decision_without_state_update',S,'state=new.payload(),observed_risk=new.risk','state=state.payload(),observed_risk=state.risk','test_golden_sequential_vs_optimized')
add('retry_bypasses_signal_identity_fence',S,'if inserted is None:return None','if inserted is None:pass','test_golden_sequential_vs_optimized')
add('duplicate_proposal_with_uniqueness_fence_removed',S,"                connection.execute(intents.insert().values(id=intent_id,decision_id=decision_id,device_id=signal.device_id,\n                    command=command,status=command['status'],created_at=now));request=command", "                connection.execute(text('ALTER TABLE policy_control_intents DROP CONSTRAINT policy_control_intents_decision_id_key'))\n                connection.execute(intents.insert().values(id=intent_id,decision_id=decision_id,device_id=signal.device_id,command=command,status=command['status'],created_at=now))\n                connection.execute(intents.insert().values(id=str(uuid.uuid4()),decision_id=decision_id,device_id=signal.device_id,command=command,status=command['status'],created_at=now));request=command",'test_retry_restart_does_not_duplicate_proposed_intent_or_guard')
add('new_version_uses_default_old_rules',W,"context=BatchRules(version,Rules.parse(active['config']))","context=BatchRules(version,Rules())",'test_new_version_uses_its_rules_and_context_cannot_cross_version')
add('worker_writes_obsolete_active_version',W,"active=c.execute(select(versions).where(versions.c.active.is_(True))).mappings().one()","active=c.execute(select(versions).where(versions.c.version=='v1')).mappings().one()",'test_version_activation_waits_for_batch_and_retains_all_sources')
add('research_result_becomes_trusted',E,"effective_security_state='unconfirmed',trusted_detector=False","effective_security_state='unconfirmed',trusted_detector=True",'test_full_queue_golden_matches_original_sequential_fair_poll')
add('missing_ml_becomes_normal',E,"s.healthy_count>=2 and s.ml_available and s.last_ml_at and (now-utc(s.last_ml_at)).total_seconds()<=rules.ml_fresh_seconds","s.healthy_count>=2",'test_golden_sequential_vs_optimized')
add('stale_and_future_detection_disabled',E,'if age>rules.max_age_seconds or age < -rules.future_skew_seconds:','if False:','test_policy_engine.py::test_stale_late_future_and_unattributed_do_not_target')
add('synthetic_stale_overtakes_real_device_backlog',W,"states.c.observed_risk!='UNKNOWN',~waiting","states.c.observed_risk!='UNKNOWN'",'test_synthetic_stale_waits_for_committed_backlog_and_is_bounded')
add('source_lag_uses_heartbeat',D,"max(0,(last['created_at']-evidence).total_seconds()) if last and evidence else None","max(0,(now-rows[0]['heartbeat_at']).total_seconds()) if rows else None",'test_metrics_show_real_evidence_lag_and_overflow_not_heartbeat')
add('overflow_hidden',D,"overflow=cap['overflow'] if cap else None","overflow=0 if cap else None",'test_metrics_show_real_evidence_lag_and_overflow_not_heartbeat')
add('timestamp_cursor_loses_late_commit',M,"IF TG_TABLE_NAME='security_observations' THEN","IF TG_TABLE_NAME='security_observations' THEN\n        IF EXISTS(SELECT 1 FROM policy_signals p WHERE (p.payload->>'occurred_at')::timestamptz > NEW.occurred_at) THEN RETURN NEW; END IF;",'test_late_insert_is_discovered_and_audited')
add('concurrent_state_lost_update',S,'.with_for_update()).mappings().one()',' ).mappings().one()','test_direct_state_concurrent_distinct_events_never_lose_evidence')
add('retention_deletes_unread_despite_source_guard',W,"    ids=list(c.scalars(select(journal.c.id).where(consumed,journal.c.occurred_at<now-timedelta(days=days))","    c.execute(text('ALTER TABLE security_observations DISABLE TRIGGER policy_security_retention'))\n    ids=list(c.scalars(select(journal.c.id).where(journal.c.occurred_at<now-timedelta(days=days))",'test_retention_never_removes_pending_and_preserves_identity')
add('source_identity_changes_on_retry',W,'                process(c,signal,version,now,batch_rules=context)',"                from dataclasses import replace\n                import uuid\n                signal=replace(signal,event_id=signal.event_id+':'+uuid.uuid4().hex[:8])\n                process(c,signal,version,now,batch_rules=context)",'test_retry_restart_does_not_duplicate_proposed_intent_or_guard')
add('unknown_ml_device_is_bound',W,"if not c.scalar(select(devices.c.device_id).where(devices.c.device_id==signal.device_id,devices.c.key_epoch==signal.key_epoch,devices.c.enabled.is_(True))):raise ValueError('Device binding unavailable')","if False:raise ValueError('Device binding unavailable')",'test_ml_contract_rejection_is_durable_and_never_authenticated')
add('policy_forges_manual_authorization_and_creates_live_command',S,'    if before_commit:before_commit()',"    if signal.device_id=='raspb1' and result['transitioned']:\n        from src.device_control import server as forbidden,models as cm\n        if not connection.scalar(select(cm.commands.c.id).limit(1)):forbidden.request_switch(connection,'raspb1','aes-128-gcm-v1','admin:forged-policy',mode=forbidden.MODE)\n    if before_commit:before_commit()",'test_policy_observations_cannot_create_live_control_commands')
add('rollback_leaves_committed_processing_markers',W,'        if before_commit:before_commit()','        if before_commit:c.commit();before_commit()','test_batch_rollback_and_retry_leave_no_partial_fsm_or_marker')
add('restart_resets_guard_without_evidence',W,'        if maintenance:\n',"        if not count:c.execute(update(states).values(state=states.c.state.op('||')({'guard':'NORMAL','risk':'NORMAL'}),observed_risk='NORMAL'))\n        if maintenance:\n",'test_retry_restart_does_not_duplicate_proposed_intent_or_guard')


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--only');p.add_argument('--source-sha',required=True);a=p.parse_args()
    if a.output.exists():p.error('Immutable report exists')
    if not os.environ.get('TEST_DATABASE_URL'):p.error('Disposable PostgreSQL required')
    root=Path.cwd();env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1');results=[]
    baseline=subprocess.run([sys.executable,'-m','pytest','-q','-p','no:cacheprovider','tests/test_policy_throughput.py','tests/test_policy_engine.py'],capture_output=True,text=True,env=env,timeout=150)
    if baseline.returncode:raise RuntimeError('Unmutated behavior failed: '+baseline.stdout[-2500:])
    for name,path,old,new,test in CASES:
        if a.only and a.only!=name:continue
        with tempfile.TemporaryDirectory(prefix='lcm-policy13-mutation-') as temp:
            temp=Path(temp)
            for folder in ['src','tests','scripts','migrations']:
                shutil.copytree(root/folder,temp/folder,ignore=shutil.ignore_patterns('__pycache__','*.zip','*.pcap','*.pcapng','*.csv','*.pkl','*.joblib','Edge-IIoTset dataset'))
            for file in ['alembic.ini','pyproject.toml']:shutil.copyfile(root/file,temp/file)
            target=temp/path;s=target.read_text()
            if old not in s:raise RuntimeError('Mutation target missing: '+name)
            target.write_text(s.replace(old,new,1))
            r=subprocess.run([sys.executable,'-m','pytest','-q','-p','no:cacheprovider','tests/'+test],cwd=temp,env=env,capture_output=True,text=True,timeout=90)
            invalid=any(v in r.stdout+r.stderr for v in ['SyntaxError','ImportError','ModuleNotFoundError','ERROR collecting'])
            killed=r.returncode==1 and not invalid
            results.append(dict(injected_defect=name,file=path,test=test,expected='behavioral failure',actual=r.stdout[-7000:]+r.stderr[-1500:],exit_code=r.returncode,behaviorally_detected=killed))
            a.output.with_suffix('.progress.json').write_text(json.dumps(results,indent=2))
    report=dict(source_sha=a.source_sha,source_hashes={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in [W,S,E,D,M]},baseline_exit=baseline.returncode,baseline_output=baseline.stdout,results=results,all_killed=all(v['behaviorally_detected'] for v in results),exit_code=0 if all(v['behaviorally_detected'] for v in results) else 1)
    a.output.write_text(json.dumps(report,indent=2));print(json.dumps(dict(killed=sum(v['behaviorally_detected'] for v in results),total=len(results),exit_code=report['exit_code'])));raise SystemExit(report['exit_code'])
if __name__=='__main__':main()

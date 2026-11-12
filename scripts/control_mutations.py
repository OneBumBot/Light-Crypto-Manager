"""Targeted behavior mutations in temporary copies; own disposable PG schemas."""
import argparse,os,sys,shutil,subprocess,tempfile,json
from pathlib import Path

MUTATIONS=[
 ('unhashable_outer_profile','src/telemetry.py',"type(packet['profile']) is not str or ",'','test_telemetry_security.py::test_outer_profile_exact_rejection'),
 ('parser_raises_type_error','src/telemetry.py',"raise InvalidTelemetry('Invalid authenticated telemetry')","raise TypeError('Invalid authenticated telemetry')",'test_telemetry_security.py::test_outer_profile_exact_rejection'),
 ('missing_profile_binding','src/telemetry.py'," or metadata['profile']!=packet['profile']",'','test_telemetry_security.py::test_aad_profile_binding_before_decrypt'),
 ('missing_key_reference','src/device_control/protocol.py',"if type(d['key_reference']) is not str or d['key_reference']!=d['requested_profile']+':'+str(d['command_epoch']):raise ValueError('Key reference')",'pass','test_control_protocol.py::test_authenticated_malformed_command_preserves_sqlite'),
 ('ack_after_pg_failure','src/brocker/mqtt_brocker.py',"logger.error(\"MQTT packet processing failed (%s)\", type(error).__name__)","client.ack(msg.mid,msg.qos)\n        logger.error(\"MQTT packet processing failed (%s)\", type(error).__name__)",'test_ingestion_ack.py::test_pg_failure_disconnects_without_ack'),
 ('ignore_control_mac','src/device_control/protocol.py',"if not hmac.compare_digest(mac,expected):",'if False:', 'test_control_protocol.py::test_control_authenticated_direction_and_device'),
 ('disable_control_replay','src/device_control/state.py',"if d['command_epoch']!=self.epoch or seq<=s['seq']:",'if False:', 'test_control_protocol.py::test_monotonic_replay_gap_rejected'),
 ('premature_effective','src/device_control/server.py',".values(command_acknowledged=data['command_sequence'])",".values(command_acknowledged=data['command_sequence'],effective_profile=data['requested_profile'])",'test_control_storage.py::test_effective_requires_real_telemetry_and_ack_loss_does_not_downgrade'),
 ('missing_device_binding','src/device_control/protocol.py',"body['device_id']!=device or ",'','test_control_protocol.py::test_authenticated_claimed_device_mismatch'),
 ('unsupported_capability','src/device_control/server.py',"if target not in d['capabilities']:",'if False:','test_control_storage.py::test_capability_rejection_creates_no_command'),
 ('repeat_nonce_range','src/device_control/state.py','rollback=first<=high','rollback=False','test_control_recovery.py::test_server_range_rollback_is_detected_on_device'),
 ('commit_before_atomic_completion','src/device_control/server.py','    return True\n\n\ndef authorize','    c.commit()\n    return True\n\n\ndef authorize','test_control_recovery.py::test_ack_transaction_rollback_does_not_queue_activate'),
 ('accept_contradictory_ack','src/device_control/server.py',"if data[field]!=source[field]:raise ValueError('ACK command binding')",'pass','test_control_recovery.py::test_forged_and_mismatched_ack_do_not_activate'),
 ('ignore_aes_authentication_failure','src/crypto_profiles.py',"lambda k,n,a,c: AESGCM(k).decrypt(n,c,a)","lambda k,n,a,c: b'unauthenticated'",'test_aes_profiles.py::test_aes_rejects_modifications[tag]'),
]


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if not os.environ.get('TEST_DATABASE_URL'):p.error('Disposable PostgreSQL TEST_DATABASE_URL required')
    root=Path.cwd();results=[]
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
    baseline=subprocess.run([sys.executable,'-m','pytest','-q','-p','no:cacheprovider','tests/test_aes_profiles.py','tests/test_control_protocol.py','tests/test_control_storage.py','tests/test_control_recovery.py'],capture_output=True,text=True,env=env,timeout=90)
    if baseline.returncode:raise RuntimeError('Unmutated baseline failed: '+baseline.stdout[-1500:])
    for defect,file,old,new,test in MUTATIONS:
        with tempfile.TemporaryDirectory(prefix='lcm-control-mutation-') as tmp:
            tmp=Path(tmp)
            for folder in ['src','tests','scripts','migrations']:
                shutil.copytree(root/folder,tmp/folder,ignore=shutil.ignore_patterns('__pycache__','*.ipynb','*.zip','Edge-IIoTset dataset'))
            shutil.copyfile(root/'alembic.ini',tmp/'alembic.ini');shutil.copyfile(root/'pyproject.toml',tmp/'pyproject.toml')
            path=tmp/file;content=path.read_text()
            if old not in content:raise ValueError('Stale mutation selector: '+defect)
            path.write_text(content.replace(old,new,1))
            run=subprocess.run([sys.executable,'-m','pytest','-q','-p','no:cacheprovider','tests/'+test],cwd=tmp,capture_output=True,text=True,env=dict(env,PYTHONPATH=str(tmp)),timeout=60)
            killed=run.returncode==1 and 'FAILED' in run.stdout and not any(x in run.stdout for x in ['ERROR collecting','SyntaxError','ModuleNotFoundError'])
            results.append(dict(injected_defect=defect,test=test,expected='behavioral assertion failure',exit_code=run.returncode,observed='killed' if killed else 'SURVIVED_OR_INVALID',output_tail=run.stdout[-1600:]))
    report=dict(schema_version=1,environment='temporary copies; real isolated PostgreSQL schemas; public fixture keys',baseline_exit=baseline.returncode,baseline_output=baseline.stdout,results=results,all_killed=all(r['observed']=='killed' for r in results))
    a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
    if not report['all_killed']:raise SystemExit(1)

if __name__=='__main__':main()

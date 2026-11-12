"""Temporary-copy behavioral mutations of UI authority boundaries; real PG schemas."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

MUTATIONS=[
 ('policy_heartbeat_refreshes_stale_evidence','src/web/monitoring.py'," or p['evidence_stale']",'','test_monitoring.py::test_fresh_policy_heartbeat_does_not_refresh_old_evidence'),
 ('identity_db_failure_unhandled','src/web/app.py',"    except SQLAlchemyError:\n        app.logger.warning('Authentication database temporarily unavailable')\n        abort(503, description='PostgreSQL недоступна. Актуальные права доступа проверить невозможно.')\n",'', 'test_monitoring.py::test_database_failure_during_identity_load_returns_unavailable'),
 ('ack_as_effective','src/web/monitoring.py',"effective_profile=state.get('effective_profile') if verified else None", "effective_profile=state.get('reported_profile') or state.get('effective_profile')",'test_monitoring.py::test_snapshot_ack_is_not_effective_and_identity_is_bound'),
 ('viewer_can_command','src/device_control/web.py',"if current_user.role!='admin':abort(403)",'if False:abort(403)','test_control_storage.py::test_control_web_roles_csrf_and_fields'),
 ('stale_is_recent','src/web/monitoring.py',"return 'recent' if 0 <= (now-timestamp).total_seconds() <= TELEMETRY_TTL else 'stale'","return 'recent'",'test_monitoring.py::test_freshness_is_admission_age_not_presence'),
 ('mongo_outage_as_available','src/web/monitoring.py',"dict(status='unavailable',checked_at=datetime.now(timezone.utc).isoformat(),source='Mongo bounded authenticated read')","dict(status='available',checked_at=datetime.now(timezone.utc).isoformat(),source='Mongo bounded authenticated read')",'test_monitoring.py::test_monitoring_api_mongo_failure_independent_rbac_limits'),
 ('research_trust_claim','src/web/monitoring.py',"trusted_detector=False,source='ml_models", "trusted_detector=True,source='ml_models",'test_monitoring.py::test_monitoring_api_mongo_failure_independent_rbac_limits'),
 ('cross_device_result','src/web/monitoring.py',"if device: q=q.where(devices.c.device_id==device)",'if False: pass','test_monitoring.py::test_monitoring_api_mongo_failure_independent_rbac_limits'),
 ('expired_still_active','src/web/monitoring.py',",control.transitions.c.deadline>now",'','test_monitoring.py::test_expired_transition_snapshot_is_uncertain_not_active'),
 ('research_actor_can_authorize','src/device_control/server.py',"or not actor.startswith('admin:')",'','test_control_storage.py::test_research_and_simulated_sources_cannot_authorize'),
]


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if not os.environ.get('TEST_DATABASE_URL'):p.error('Disposable PostgreSQL required')
    if a.output.exists():p.error('Immutable output exists')
    baseline=subprocess.run([sys.executable,'-m','pytest','-q','-p','no:cacheprovider','tests/test_monitoring.py','tests/test_control_storage.py::test_control_web_roles_csrf_and_fields','tests/test_control_storage.py::test_research_and_simulated_sources_cannot_authorize'],capture_output=True,text=True,timeout=90)
    if baseline.returncode:raise RuntimeError('Baseline failed: '+baseline.stdout[-2500:])
    results=[];root=Path.cwd()
    for defect,file,old,new,test in MUTATIONS:
        with tempfile.TemporaryDirectory(prefix='stage9-mutation-') as temporary:
            tmp=Path(temporary)
            for folder in ['src','tests','scripts','migrations']:
                shutil.copytree(root/folder,tmp/folder,ignore=shutil.ignore_patterns('__pycache__','*.zip','*.pcap','*.csv','*.joblib','*.ipynb','Edge-IIoTset dataset'))
            for name in ['alembic.ini','pyproject.toml']:shutil.copyfile(root/name,tmp/name)
            path=tmp/file;source=path.read_text()
            if old not in source:raise ValueError('Stale mutation selector: '+defect)
            path.write_text(source.replace(old,new,1))
            r=subprocess.run([sys.executable,'-m','pytest','-q','-p','no:cacheprovider','tests/'+test],cwd=tmp,env=dict(os.environ,PYTHONPATH=str(tmp),PYTHONDONTWRITEBYTECODE='1'),capture_output=True,text=True,timeout=90)
            killed=r.returncode==1 and 'FAILED' in r.stdout and not any(x in r.stdout for x in ['ERROR collecting','SyntaxError','ModuleNotFoundError','ImportError'])
            results.append(dict(injected_defect=defect,test=test,expected='behavioral assertion failure',actual=r.stdout[-2500:],exit_code=r.returncode,behaviorally_detected=killed))
    report=dict(baseline_exit_code=baseline.returncode,baseline=baseline.stdout,results=results,all_killed=all(x['behaviorally_detected'] for x in results))
    a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
    if not report['all_killed']:raise SystemExit(1)

if __name__=='__main__':main()

"""Controlled real-agent missing/stale SQLite experiments, dedicated Stage11 only.

Backups remain private. Restore only the captured current authority, never reset.
"""
import argparse,json,time
from pathlib import Path
from scripts.kuz_lab import Lab
from scripts.performance_run import login
from scripts.performance_reliability import switch,wait
from src.crypto_profiles import ASCON,KUZ


def main():
    p=argparse.ArgumentParser();p.add_argument('--directory',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():p.error('Immutable report exists')
    lab=Lab(a.directory);s,url,token=login(lab)
    def run_python(code):return lab.run('run','--rm','-T','--no-deps','--entrypoint','python','device-alpha','-c',code)
    def alpha():return lab.probe('snapshot')['per_device']['alpha']['count']
    def profile():return next(d for d in lab.probe('snapshot')['devices'] if d['device_id']=='alpha')['effective_profile']
    assert profile()==ASCON
    run_python("import sqlite3,os;from pathlib import Path;p=Path('/device/stage11-stale-ascon.db');assert not p.exists();sqlite3.connect('/device/device.db').backup(sqlite3.connect(p));os.chmod(p,0o600)")
    transition=switch(lab,s,url,token,'alpha',KUZ);lab.run('stop','device-alpha')
    run_python("import sqlite3,os;from pathlib import Path;p=Path('/device/stage11-current-mgm.db');assert not p.exists();sqlite3.connect('/device/device.db').backup(sqlite3.connect(p));os.chmod(p,0o600)")
    try:
        run_python("import shutil;shutil.copyfile('/device/stage11-stale-ascon.db','/device/device.db')")
        before=alpha();lab.run('up','-d','--no-deps','device-alpha');time.sleep(5)
        assert alpha()==before and profile()==KUZ
    finally:
        lab.run('stop','device-alpha')
        run_python("import shutil;shutil.copyfile('/device/stage11-current-mgm.db','/device/device.db')")
        lab.run('up','-d','--no-deps','--wait','device-alpha')
    wait(lambda:alpha()>before,30)
    assert profile()==KUZ
    lab.run('stop','device-alpha');before_missing=alpha()
    try:
        run_python("import os;from pathlib import Path;assert not Path('/device/stage11-missing-current.db').exists();os.rename('/device/device.db','/device/stage11-missing-current.db')")
        failed=lab.run('run','--rm','-T','--no-deps','device-alpha',check=False,timeout=15)
        assert failed.returncode!=0 and 'Device state missing' in failed.stderr
        run_python("from pathlib import Path;assert not Path('/device/device.db').exists()")
        assert alpha()==before_missing and profile()==KUZ
    finally:
        run_python("import os;from pathlib import Path;p=Path('/device/stage11-missing-current.db');assert p.exists();os.rename(p,'/device/device.db')")
        lab.run('up','-d','--no-deps','--wait','device-alpha')
    wait(lambda:alpha()>before_missing,30);assert profile()==KUZ
    back=switch(lab,s,url,token,'alpha',ASCON)
    a.output.write_text(json.dumps(dict(project=lab.project,stale_restore_no_admission=True,no_silent_downgrade=True,missing_state_agent_exit=failed.returncode,missing_state_no_reinitialization=True,current_state_restore_requires_new_grant=True,real_transitions=[transition,back],commands=lab.commands,exit_code=0),indent=2))
    print('Actual MGM agent stale/missing SQLite fail-closed and current-state recovery: exit 0')

if __name__=='__main__':main()

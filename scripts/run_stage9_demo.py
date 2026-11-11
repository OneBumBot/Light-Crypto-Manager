"""Start new or resume saved stage9 state. Stop retains all keys/volumes/counters."""
import argparse
import json
import subprocess
from pathlib import Path
from scripts.stage9_common import Demo


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',type=Path,required=True)
    p.add_argument('action',choices=['start','stop','status'],default='start',nargs='?');p.add_argument('--build',action='store_true')
    a=p.parse_args();d=Demo(a.directory);marker=d.root/'used-volumes.json'
    if a.action=='stop':
        d.run('stop');print('Stopped; keys, volumes and nonce/command state retained.');return
    if a.action=='status':
        print(json.dumps(d.probe('status'),indent=2));return
    if marker.exists():
        expected=json.loads(marker.read_text())
        for volume in expected:
            if not volume.startswith(d.project+'_'):raise ValueError('Volume identity mismatch')
            if subprocess.run(['docker','volume','inspect',volume],capture_output=True).returncode:
                raise ValueError('Used volume missing; reviewed recovery required; refusing reinitialization')
    else:
        # Persist intent before startup. A failed partial initialization needs operator review.
        expected=[d.project+'_'+v for v in ['postgres-data','mongo-data','alpha-control','beta-control','gamma-control']]
        for volume in expected:
            name=volume[len(d.project)+1:]
            subprocess.run(['docker','volume','create','--label','com.docker.compose.project='+d.project,'--label','com.docker.compose.volume='+name,volume],check=True,stdout=subprocess.DEVNULL)
        marker.write_text(json.dumps(expected));marker.chmod(0o600)
    if a.build:d.run('build','receiver','tests',timeout=600)
    d.run('up','-d','--wait','--wait-timeout','120','postgres','mongo','broker','receiver','outbox-relay','web','policy-worker')
    d.run('run','--rm','--no-deps','control-init')
    d.probe('setup')
    d.run('up','-d','--wait','--wait-timeout','90','control-worker','device-alpha','device-beta','device-gamma')
    result=d.probe('ready')
    (d.root/'last-start.json').write_text(json.dumps(dict(project=d.project,url=d.url(),status=result,commands=d.commands),indent=2))
    (d.root/'last-start.json').chmod(0o600)
    print(json.dumps(dict(url=d.url(),devices=result['devices'],policy='DRY_RUN',control='MANUAL_AUTHORIZED_CONTROL',
        ml='disabled; trusted_detector=false',accounts='demo-admin / demo-operator / demo-viewer; passwords in private accounts directory'),indent=2))

if __name__=='__main__':main()

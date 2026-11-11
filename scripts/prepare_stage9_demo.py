"""Create a NEW isolated three-device demo. Existing project/state is never reset."""
import argparse
import json
import os
import re
import secrets
import subprocess
from pathlib import Path
from scripts.prepare_control import prepare


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--directory',type=Path,required=True);p.add_argument('--project',required=True)
    a=p.parse_args()
    if not re.fullmatch(r'lcm-stage9-demo-[a-z0-9-]{1,20}',a.project):p.error('Dedicated lcm-stage9-demo-* name required')
    if a.directory.exists():p.error('Directory exists; use run_stage9_demo to resume')
    for kind in ['volume','network','container']:
        found=subprocess.check_output(['docker',kind,'ls','-q','--filter','label=com.docker.compose.project='+a.project])
        if found.strip():p.error('Project already used; choose a new name, never reset volumes')
    prepare(a.directory,a.project)
    root=a.directory.resolve();registry=json.loads((root/'mqtt/registry.json').read_text())
    # Only these identities are provisioned to stage9, unlike the older general stage8 lab.
    (root/'mqtt/registry.json').write_text(json.dumps({k:v for k,v in registry.items() if k in ['alpha','beta','gamma']}))
    accounts=root/'accounts';accounts.mkdir(mode=0o700)
    for role in ['admin','operator','viewer']:
        target=accounts/(role+'.password');target.write_text(secrets.token_urlsafe(30)+'\n');target.chmod(0o600)
    (root/'stage9.json').write_text(json.dumps(dict(project=a.project,schema=1,devices=['alpha','beta','gamma'])))
    (root/'stage9.json').chmod(0o600)
    print('New private stage9 demo prepared. Account names: demo-admin / demo-operator / demo-viewer.')
    print('Passwords remain in '+str(accounts)+' (0600). No password printed.')

if __name__=='__main__':main()

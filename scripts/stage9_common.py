"""Local-only orchestration guard and bounded subprocess wrapper. Never deletes state."""
import json
import re
import subprocess
from pathlib import Path


class Demo:
    def __init__(self,directory):
        self.root=Path(directory).resolve()
        if self.root.stat().st_mode & 0o077:raise ValueError('Private demo directory required')
        stage16=(self.root/'stage16.json').exists()
        identity=json.loads((self.root/('stage16.json' if stage16 else 'stage9.json')).read_text())
        self.project=identity['project']
        if not re.fullmatch(r'lcm-stage16-final-demo-[a-z0-9-]{1,18}' if stage16 else r'lcm-stage9-demo-[a-z0-9-]{1,20}',self.project):raise ValueError('Dedicated demo project required')
        values=dict(line.split('=',1) for line in (self.root/'compose.env').read_text().splitlines() if '=' in line and not line.startswith('#'))
        if values.get('COMPOSE_PROJECT_NAME')!=self.project:raise ValueError('Project mismatch')
        if values.get('CONTROL_INPUT_DIR')!=str(self.root):raise ValueError('Private input mismatch')
        if values.get('CONTROL_MODE')!='MANUAL_AUTHORIZED_CONTROL':raise ValueError('Manual control required')
        self.base=['docker','compose','--env-file',str(self.root/'compose.env'),'-f','compose.yaml','-f','compose.control.yaml','-f','compose.stage9.yaml','--profile','control','--profile','web','--profile','policy']
        if stage16:
            where=self.base.index('--profile');self.base[where:where]=['-f','compose.stage16.yaml','-f',str(self.root/'network.json')]
        self.commands=[]

    def run(self,*args,check=True,timeout=180,input_data=None):
        r=subprocess.run(self.base+list(args),capture_output=True,text=True,timeout=timeout,input=input_data)
        self.commands.append(dict(command=self.base+list(args),exit_code=r.returncode))
        if r.returncode:
            (self.root/'last-command-failure.txt').write_text(r.stdout+r.stderr)
            (self.root/'last-command-failure.txt').chmod(0o600)
        if check and r.returncode:raise RuntimeError('Demo command failed: '+args[0]+' ('+str(r.returncode)+'); '+r.stderr[-500:])
        return r

    def probe(self,action):
        payload=json.dumps({role:(self.root/'accounts'/(role+'.password')).read_text().strip() for role in ['admin','operator','viewer']}) if action=='setup' else None
        r=self.run('run','--rm','-T','--no-deps','--entrypoint','python','tests','-m','scripts.stage9_probe',action,input_data=payload)
        return json.loads(r.stdout[r.stdout.index('{'):])

    def url(self):
        binding=self.run('port','web','5000').stdout.strip()
        if not binding.startswith('127.0.0.1:'):raise ValueError('Local-only web binding required')
        return 'http://'+binding

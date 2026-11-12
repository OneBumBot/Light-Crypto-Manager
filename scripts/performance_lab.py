"""Dedicated stage10 software lab. No production/previous-stage volumes or keys."""
import argparse,json,os,re,secrets,subprocess,sys,time
from pathlib import Path
from src.device_control.state import DeviceState
from src.crypto_profiles import ASCON,AES

PREFIX=re.compile(r'lcm-stage10-performance-[a-z0-9-]{1,18}\Z')

class Lab:
    def __init__(self,directory):
        self.root=Path(directory).resolve()
        if self.root.stat().st_mode&0o077:raise ValueError('Private directory required')
        self.manifest=json.loads((self.root/'stage10.json').read_text());self.project=self.manifest['project'];self.devices=self.manifest['devices']
        if not PREFIX.fullmatch(self.project) or not 1<=len(self.devices)<=50:raise ValueError('Dedicated bounded stage10 lab required')
        env=dict(l.split('=',1) for l in (self.root/'compose.env').read_text().splitlines() if '=' in l and not l.startswith('#'))
        if env.get('COMPOSE_PROJECT_NAME')!=self.project or env.get('CONTROL_INPUT_DIR')!=str(self.root):raise ValueError('Lab identity mismatch')
        self.base=['docker','compose','--env-file',str(self.root/'compose.env'),'-f','compose.yaml','-f','compose.control.yaml','-f',str(self.root/'performance.compose.json'),'--profile','control','--profile','web','--profile','policy'];self.commands=[]
    def run(self,*args,check=True,timeout=180,input_data=None):
        r=subprocess.run(self.base+list(args),capture_output=True,text=True,timeout=timeout,input=input_data)
        self.commands.append(dict(command=self.base+list(args),exit_code=r.returncode))
        if r.returncode:
            p=self.root/'last-failure.txt';p.write_text(r.stdout+r.stderr);p.chmod(0o600)
            if check:raise RuntimeError('Lab command '+args[0]+' failed ('+str(r.returncode)+'); private last-failure.txt')
        return r
    def url(self):
        value=self.run('port','web','5000').stdout.strip()
        if not value.startswith('127.0.0.1:'):raise ValueError('Loopback binding required')
        return 'http://'+value
    def probe(self,action,**kwargs):
        r=self.run('run','--rm','-T','--no-deps','--entrypoint','python','tests','-m','scripts.performance_probe',action,input_data=json.dumps(kwargs) if kwargs else None)
        return json.loads(r.stdout[r.stdout.index('{'):])
    def agents(self,n=None):return ['device-'+d for d in self.devices[:n]]


def prepare(root,project,count):
    if not PREFIX.fullmatch(project or '') or count not in [3,10,25,50]:raise ValueError('Stage10 project and 3/10/25/50 devices required')
    if root.exists():raise ValueError('New directory required; never reset existing state')
    for kind in ['volume','network','container']:
        if subprocess.check_output(['docker',kind,'ls','-q','--filter','label=com.docker.compose.project='+project]).strip():raise ValueError('Project already exists')
    os.umask(0o077);root.mkdir(parents=True,mode=0o700);root=root.resolve()
    devices=['alpha','beta','gamma']+[f'dev{i:03}' for i in range(4,count+1)]
    subprocess.run([sys.executable,'-m','scripts.prepare_compose','--env-file',str(root/'compose.env'),'--project',project,'--mqtt-port','0','--web-port','0'],check=True)
    args=[sys.executable,'-m','scripts.prepare_security','--directory',str(root/'mqtt')]
    for d in devices:args+=['--extra-device',d]
    subprocess.run(args,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    subprocess.run([sys.executable,'-m','scripts.prepare_storage','--directory',str(root/'mongo')],check=True)
    registry=json.loads((root/'mqtt/registry.json').read_text());registry={d:registry[d] for d in devices};control={}
    for d in devices:
        registry[d]['telemetry_keys']={'AES-128-GCM':secrets.token_hex(16)}
        control[d]=dict(registry=registry[d],command_key=secrets.token_hex(32),status_key=secrets.token_hex(32),capabilities=[ASCON] if d=='gamma' else [ASCON,AES],command_epoch=1)
        folder=root/d;folder.mkdir(mode=0o700)
        (folder/'control.json').write_text(json.dumps({d:control[d]}))
        for name in ['ca.crt','device_'+d+'.password']:(folder/name).write_bytes((root/'mqtt'/name).read_bytes())
        state=DeviceState(folder/'device.db',d,1,initialize=True);state.close()
    (root/'control.json').write_text(json.dumps(control));(root/'mqtt/registry.json').write_text(json.dumps(registry))
    password=secrets.token_hex(24);(root/'mqtt/controller.password').write_text(password+'\n')
    from scripts.prepare_security import BROKER_IMAGE
    subprocess.run(['docker','run','--rm','-i','--user',f'{os.getuid()}:{os.getgid()}','--mount',f'type=bind,source={root/"mqtt"},target=/work','--entrypoint','mosquitto_passwd',BROKER_IMAGE,'/work/passwords','controller'],input=(password+'\n'+password+'\n').encode(),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
    accounts=root/'accounts';accounts.mkdir(mode=0o700)
    for role in ['admin','viewer','operator']:(accounts/(role+'.password')).write_text(secrets.token_urlsafe(30)+'\n')
    manifest=dict(project=project,devices=devices,schema_version=1,private_material='fresh independent per identity')
    (root/'stage10.json').write_text(json.dumps(manifest))
    env=(root/'compose.env').read_text().replace('MQTT_SECURITY_DIR=.local-runtime/security','MQTT_SECURITY_DIR='+str(root/'mqtt')).replace('MONGO_SECURITY_DIR=.local-runtime/mongo-security','MONGO_SECURITY_DIR='+str(root/'mongo'))
    env+='\nCONTROL_INPUT_DIR='+str(root)+'\nCONTROL_MODE=MANUAL_AUTHORIZED_CONTROL\n'
    (root/'compose.env').write_text(env)
    services={'web':{'environment':{'WEB_MQTT_ENABLED':'0','ML_MONITOR_MODE':'DISABLED'}},'receiver':{'environment':{'MQTT_CLIENT_ID':project+'-receiver'}},
        'control-init':{'command':['python','-m','scripts.install_stage10'],'volumes':[str(root)+':/input:ro','control-security:/out/controller']}}
    volumes={}
    for d in devices:
        volume=d+'-control';volumes[volume]={};services['control-init']['volumes'].append(volume+':/out/'+d)
        services['device-'+d]={'image':project+'-runtime','profiles':['control'],'init':True,'command':['python','-m','src.device_control.agent'],
            'cpus':.25,'mem_limit':'128m','cap_drop':['ALL'],'logging':{'driver':'json-file','options':{'max-size':'2m','max-file':'2'}},
            'environment':{'MQTT_HOST':'broker','MQTT_PORT':'8883','MQTT_USERNAME':'device_'+d,'MQTT_PASSWORD_FILE':'/device/device_'+d+'.password','MQTT_CA_FILE':'/device/ca.crt','CONTROL_KEYS_FILE':'/device/control.json','DEVICE_ID':d,'DEVICE_STATE_FILE':'/device/device.db','PUBLISH_INTERVAL':'${STAGE10_INTERVAL:-0.5}','AGENT_EXPERIMENT_FILE':'/device/research-events.jsonl','AGENT_EXPERIMENT_MAX_EVENTS':'50000'},
            'volumes':[volume+':/device'],'depends_on':{'control-init':{'condition':'service_completed_successfully'},'receiver':{'condition':'service_healthy'},'control-worker':{'condition':'service_healthy'}},
            'healthcheck':{'test':['CMD','python','-c',"from pathlib import Path;assert Path('/tmp/device-ready').exists()"],'interval':'5s','retries':20},'stop_grace_period':'10s'}
    (root/'performance.compose.json').write_text(json.dumps(dict(services=services,volumes=volumes),indent=2))
    for path in root.rglob('*'):
        if path.is_file():path.chmod(0o600)
    print('Fresh isolated performance inputs prepared:',project,'devices:',count,'secrets withheld')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['prepare','start','stop','status']);p.add_argument('--directory',type=Path,required=True);p.add_argument('--project');p.add_argument('--devices',type=int,default=3);p.add_argument('--build',action='store_true');a=p.parse_args()
    if a.action=='prepare':prepare(a.directory,a.project,a.devices);return
    lab=Lab(a.directory)
    if a.action=='stop':lab.run('stop');print('Stopped; all state/keys/volumes retained');return
    if a.action=='status':print(json.dumps(lab.probe('snapshot'),indent=2));return
    marker=lab.root/'used-volumes.json'
    if marker.exists():
        for v in json.loads(marker.read_text()):
            if not v.startswith(lab.project+'_') or subprocess.run(['docker','volume','inspect',v],capture_output=True).returncode:raise ValueError('Used state volume missing; recovery required')
    else:
        names=['postgres-data','mongo-data']+[d+'-control' for d in lab.devices]
        for n in names:subprocess.run(['docker','volume','create','--label','com.docker.compose.project='+lab.project,'--label','com.docker.compose.volume='+n,lab.project+'_'+n],check=True,stdout=subprocess.DEVNULL)
        marker.write_text(json.dumps([lab.project+'_'+n for n in names]));marker.chmod(0o600)
    if a.build:lab.run('build','receiver','tests',timeout=600)
    lab.run('up','-d','--wait','--wait-timeout','120','postgres','mongo','broker','receiver','outbox-relay','web','policy-worker')
    lab.run('run','--rm','--no-deps','control-init')
    credentials={r:(lab.root/'accounts'/(r+'.password')).read_text().strip() for r in ['admin','operator','viewer']}
    lab.run('run','--rm','-T','--no-deps','--entrypoint','python','tests','-m','scripts.stage9_probe','setup',input_data=json.dumps(credentials))
    lab.run('up','-d','--wait','--wait-timeout','120','control-worker',*lab.agents())
    end=time.monotonic()+90
    while time.monotonic()<end:
        status=lab.probe('snapshot')
        if len(status['devices'])==len(lab.devices) and all(d['effective_event'] for d in status['devices']) and status['mongo_managed']>=len(lab.devices):break
        time.sleep(.5)
    else:raise AssertionError('First actual telemetry not observed')
    print(json.dumps(dict(project=lab.project,url=lab.url(),devices=len(lab.devices),policy='DRY_RUN',control='MANUAL_AUTHORIZED_CONTROL',ml_trusted=False),indent=2))

if __name__=='__main__':main()

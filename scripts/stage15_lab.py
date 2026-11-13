"""Private bounded Stage15 research infrastructure; never resets used state."""
import argparse,ipaddress,json,os,re,subprocess,sys
from pathlib import Path
PREFIX=re.compile(r'lcm-stage15-shadow-ids-[a-z0-9-]{1,18}\Z')

class Lab:
 def __init__(self,root):
  self.root=Path(root).resolve();self.env=self.root/'compose.env';self.manifest=json.loads((self.root/'stage15.json').read_text());self.project=self.manifest['project'];self.commands=[]
  if not PREFIX.fullmatch(self.project) or self.root.stat().st_mode&0o077:raise ValueError('Private Stage15 lab required')
  self.base=['docker','compose','--env-file',str(self.env),'-f','compose.yaml','-f','compose.research.yaml','-f',str(self.root/'stage15.compose.json'),'--profile','research']
 def run(self,*args,timeout=180,check=True):
  r=subprocess.run(self.base+list(args),capture_output=True,text=True,timeout=timeout)
  self.commands.append(dict(command=self.base+list(args),exit_code=r.returncode))
  if r.returncode and check:
   f=self.root/'last-failure.txt';f.write_text(r.stdout+r.stderr);f.chmod(0o600);raise RuntimeError('Stage15 operation failed; see private last-failure.txt')
  return r
 def stop(self):self.run('stop');print('Stopped; all keys/state/volumes retained')


def prepare(root,project,subnet):
 if not PREFIX.fullmatch(project):raise ValueError('Dedicated Stage15 project required')
 net=ipaddress.ip_network(subnet)
 if net.version!=4 or not net.is_private or net.prefixlen!=24:raise ValueError('Private /24 required')
 if root.exists():raise ValueError('Existing input/state preserved')
 for kind in ['volume','network','container']:
  if subprocess.check_output(['docker',kind,'ls','-q','--filter','label=com.docker.compose.project='+project]).strip():raise ValueError('Project already exists')
 os.umask(0o077);root.mkdir(parents=True,mode=0o700);root=root.resolve()
 subprocess.run([sys.executable,'-m','scripts.prepare_compose','--env-file',str(root/'compose.env'),'--project',project,'--mqtt-port','0','--web-port','0'],check=True)
 subprocess.run([sys.executable,'-m','scripts.prepare_security','--directory',str(root/'mqtt')]+sum([['--extra-device',f'lab{i:03}'] for i in range(1,51)],[]),check=True,capture_output=True)
 subprocess.run([sys.executable,'-m','scripts.prepare_storage','--directory',str(root/'mongo')],check=True)
 env=(root/'compose.env').read_text().replace('MQTT_SECURITY_DIR=.local-runtime/security','MQTT_SECURITY_DIR='+str(root/'mqtt')).replace('MONGO_SECURITY_DIR=.local-runtime/mongo-security','MONGO_SECURITY_DIR='+str(root/'mongo'));(root/'compose.env').write_text(env)
 cfg=dict(networks=dict(default=dict(ipam=dict(config=[dict(subnet=str(net))]))),services={'broker':{'volumes':['stage15-broker-logs:/mosquitto/log']},'mongo':{'volumes':['stage15-mongo-config:/data/configdb']}},volumes={'stage15-broker-logs':{},'stage15-mongo-config':{}})
 (root/'stage15.compose.json').write_text(json.dumps(cfg,indent=2));(root/'stage15.json').write_text(json.dumps(dict(project=project,subnet=str(net),independent_credentials=True,schema_version=1),indent=2))
 for f in root.rglob('*'):
  if f.is_file():f.chmod(0o600)
 print('Fresh independent Stage15 inputs prepared; secret values withheld')


def main():
 p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','baseline','start','stop']);p.add_argument('--directory',type=Path,required=True);p.add_argument('--project');p.add_argument('--subnet');p.add_argument('--build',action='store_true');p.add_argument('--output',type=Path);a=p.parse_args()
 if a.action=='prepare':prepare(a.directory,a.project,a.subnet);return
 lab=Lab(a.directory)
 if a.action=='stop':lab.stop();return
 if a.build:lab.run('build','receiver','tests',*(['research-init'] if a.action=='start' else []),timeout=900)
 if a.action=='baseline':
  r=lab.run('run','--rm','-T','tests',timeout=300,check=False)
  if a.output is None:raise ValueError('Public baseline log path required')
  a.output.write_text(r.stdout+r.stderr);a.output.with_suffix('.commands.json').write_text(json.dumps(dict(commands=lab.commands,exit_code=r.returncode),indent=2));lab.stop();sys.exit(r.returncode)
 marker=lab.root/'used-volumes.json'
 if marker.exists():
  for name in json.loads(marker.read_text()):
   if not name.startswith(lab.project+'_') or subprocess.run(['docker','volume','inspect',name],capture_output=True).returncode:raise ValueError('Previously used state missing; reviewed recovery/rekey required')
 lab.run('up','-d','--wait','postgres','mongo','broker','receiver','outbox-relay','lab-devices','research-observer','traffic-collector',timeout=300)
 names=subprocess.check_output(['docker','volume','ls','--format','{{.Name}}','--filter','label=com.docker.compose.project='+lab.project],text=True).splitlines();marker.write_text(json.dumps(names));marker.chmod(0o600)
 print('Research services ready; isolated internal network, no host ports')
if __name__=='__main__':main()

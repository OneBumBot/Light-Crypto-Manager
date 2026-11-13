"""Original research artifacts are read-only; report hashes, never private bytes."""
import argparse,hashlib,json,subprocess
from pathlib import Path
BASE='b2317f94b9198b6300d49d9e5effd11a7efee298'


def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def snapshot():
 tracked={}
 for name in subprocess.check_output(['git','ls-tree','-r','--name-only',BASE],text=True).splitlines():
  if name.startswith(('docs/reports/','migrations/versions/','native/','third_party/')) or any(x in name.lower() for x in ['frozen','holdout','model_registry']):tracked[name]=sha(name)
 files={};manifest=Path('.local-runtime/ground-truth-fix/archive-hashes.json')
 if manifest.exists():
  for name,value in json.loads(manifest.read_text()).items():
   assert sha(name)==value,'Historical archive differs';files[name]=value
 for root in Path('.local-runtime').iterdir():
  if root.name=='stage16' or not root.is_dir():continue
  for f in root.rglob('*'):
   if f.is_file() and (f.suffix in ['.pcap','.pcapng','.csv','.skops','.joblib','.db','.password','.key'] or f.name in ['plan.json','freeze.json','registry.json','control.json']):files[str(f)]=sha(f)
 ids=subprocess.check_output(['docker','ps','-aq'],text=True).split();old=[]
 if ids:
  for r in json.loads(subprocess.check_output(['docker','inspect',*ids],text=True)):
   project=r.get('Config',{}).get('Labels',{}).get('com.docker.compose.project','')
   if project and not project.startswith('lcm-stage16-final-demo-'):old.append(dict(name=r['Name'],project=project,image=r['Image'],running=r['State']['Running'],started=r['State']['StartedAt'],finished=r['State']['FinishedAt']))
 volumes=[n for n in subprocess.check_output(['docker','volume','ls','--format','{{.Name}}'],text=True).splitlines() if not n.startswith('lcm-stage16-final-demo-')]
 return dict(baseline_sha=BASE,tracked=tracked,private_files=files,old_containers=sorted(old,key=lambda r:r['name']),old_volumes=sorted(volumes),main_sha=subprocess.check_output(['git','rev-parse','main'],text=True).strip())


def main():
 p=argparse.ArgumentParser();p.add_argument('phase',choices=['before','after']);p.add_argument('--before',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():p.error('Immutable audit output')
 value=snapshot()
 additions=[]
 if a.phase=='after':
  before=json.loads(a.before.read_text())['snapshot']
  extra=set(value['old_volumes'])-set(before['old_volumes'])
  ids=subprocess.check_output(['docker','ps','-aq'],text=True).split()
  for row in json.loads(subprocess.check_output(['docker','inspect',*ids],text=True)) if ids else []:
   labels=row['Config'].get('Labels') or {};project=labels.get('com.docker.compose.project','');service=labels.get('com.docker.compose.service')
   if not project.startswith('lcm-stage16-final-demo-'):continue
   for mount in row['Mounts']:
    if mount['Type']=='volume' and mount.get('Name') in extra:
     assert (service,mount['Destination']) in [('mongo','/data/configdb'),('broker','/mosquitto/log')],'Unexpected new anonymous volume'
     additions.append(dict(volume=mount['Name'],project=project,service=service,target=mount['Destination']))
  assert extra=={r['volume'] for r in additions},'Unexplained added volume'
  value['old_volumes']=[name for name in value['old_volumes'] if name not in extra]
  assert value==before,'Historical state changed'
 a.output.write_text(json.dumps(dict(snapshot=value,unchanged=True if a.phase=='after' else None,phase=a.phase,new_project_owned_auxiliary_volumes=additions,classification='New image-declared auxiliary volumes proven by actual Stage16 container bindings; every baseline file/container/volume remains identical',exit_code=0),indent=2));print('Protected artifacts checked:',len(value['tracked']),'tracked,',len(value['private_files']),'private; values withheld; exit0')
if __name__=='__main__':main()

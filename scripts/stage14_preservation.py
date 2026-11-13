"""Original research artifacts are read-only; report hashes, never private bytes."""
import argparse,hashlib,json,subprocess
from pathlib import Path
BASE='21a99bbc6669ca440a1b174e1285a24ac7b323c2'


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
  if root.name=='stage14' or not root.is_dir():continue
  for f in root.rglob('*'):
   if f.is_file() and (f.suffix in ['.pcap','.pcapng','.csv','.skops','.joblib','.db','.password','.key'] or f.name in ['plan.json','freeze.json','registry.json','control.json']):files[str(f)]=sha(f)
 ids=subprocess.check_output(['docker','ps','-aq'],text=True).split();old=[]
 if ids:
  for r in json.loads(subprocess.check_output(['docker','inspect',*ids],text=True)):
   project=r.get('Config',{}).get('Labels',{}).get('com.docker.compose.project','')
   if project and not project.startswith('lcm-stage14-ground-truth-'):old.append(dict(name=r['Name'],project=project,image=r['Image'],running=r['State']['Running'],started=r['State']['StartedAt'],finished=r['State']['FinishedAt']))
 volumes=[n for n in subprocess.check_output(['docker','volume','ls','--format','{{.Name}}'],text=True).splitlines() if not n.startswith('lcm-stage14-ground-truth-')]
 return dict(baseline_sha=BASE,tracked=tracked,private_files=files,old_containers=sorted(old,key=lambda r:r['name']),old_volumes=sorted(volumes),main_sha=subprocess.check_output(['git','rev-parse','main'],text=True).strip())


def main():
 p=argparse.ArgumentParser();p.add_argument('phase',choices=['before','after']);p.add_argument('--before',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():p.error('Immutable audit output')
 value=snapshot()
 if a.phase=='after':assert value==json.loads(a.before.read_text())['snapshot'],'Historical state changed'
 a.output.write_text(json.dumps(dict(snapshot=value,unchanged=True if a.phase=='after' else None,phase=a.phase,exit_code=0),indent=2));print('Protected artifacts checked:',len(value['tracked']),'tracked,',len(value['private_files']),'private; values withheld; exit0')
if __name__=='__main__':main()

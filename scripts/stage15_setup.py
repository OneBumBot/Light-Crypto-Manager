"""Fresh Stage15 shadow model copies and keyless role scopes, no prior volume reuse."""
import argparse,json,os,shutil,subprocess
from pathlib import Path
from scripts.stage15_lab import Lab,prepare
from src.shadow_ids.models import frozen
from src.classifier.ml.artifacts import verify

def configure(root):
 root=Path(root).resolve();models=root/'models';shadow=root/'shadow'
 if models.exists() or shadow.exists():raise ValueError('Existing Stage15 state preserved')
 os.umask(0o077);models.mkdir(mode=0o700);shadow.mkdir(mode=0o700)
 for pin in frozen().values():
  _,source=verify(Path('.local-runtime/stage14/study/models'),pin['model_id'],pin['model_version']);dest=models/pin['model_id']/pin['model_version'];dest.parent.mkdir(mode=0o700,exist_ok=True);shutil.copytree(source,dest)
 (root/'parity.json').write_text(json.dumps(dict(status='NOT_VERIFIED')))
 with (root/'compose.env').open('a') as f:f.write('\nSHADOW_UID='+str(os.getuid())+'\nSHADOW_GID='+str(os.getgid())+'\nSHADOW_ROOT='+str(shadow)+'\nSHADOW_MODELS='+str(models)+'\nSHADOW_PARITY='+str(root/'parity.json')+'\n')
 # Explicit auxiliary named volumes already set by Stage15Lab prepare.
 return root

def lab(root):
 l=Lab(root);where=l.base.index('--profile');l.base[where:where]=['-f','compose.shadow.yaml']
 from src.shadow_ids.isolation import validate
 validate(json.loads(l.run('--profile','*','config','--format','json').stdout)['services'])
 from src.shadow_ids.isolation import check_used_volumes
 marker=l.root/'used-volumes.json'
 if marker.exists():check_used_volumes(json.loads(marker.read_text()),l.project,lambda name:subprocess.run(['docker','volume','inspect',name],capture_output=True).returncode==0)
 else:
  names=subprocess.check_output(['docker','volume','ls','--format','{{.Name}}','--filter','label=com.docker.compose.project='+l.project],text=True).splitlines()
  if names:marker.write_text(json.dumps(names));marker.chmod(0o600)
 return l
def main():
 p=argparse.ArgumentParser();p.add_argument('action',nargs='?',default='prepare',choices=['prepare','start','stop']);p.add_argument('--directory',type=Path,required=True);p.add_argument('--project');p.add_argument('--subnet');p.add_argument('--build',action='store_true');a=p.parse_args()
 if a.action=='prepare':
  if not a.project or not a.subnet:p.error('Fresh project and private /24 subnet required')
  prepare(a.directory,a.project,a.subnet);configure(a.directory);print('Four pinned models copied privately; no fit, original artifacts untouched');return
 l=lab(a.directory)
 if a.action=='stop':
  ids=subprocess.check_output(['docker','ps','-q','--filter','label=com.docker.compose.project='+l.project],text=True).split()
  if ids:subprocess.run(['docker','stop',*ids],check=True,stdout=subprocess.DEVNULL,timeout=90)
  print('Stage15 services stopped; all evidence, keys and volumes retained');return
 if a.build:l.run('build','receiver','tests','research-init','shadow-network-observer','shadow-model-worker',timeout=1200)
 l.run('up','-d','--wait','postgres','mongo','broker','receiver','outbox-relay','lab-devices','research-observer','traffic-collector',timeout=300);lab(a.directory);print('Fresh bounded software stand ready; live inference remains blocked until current-source parity PASS')
if __name__=='__main__':main()

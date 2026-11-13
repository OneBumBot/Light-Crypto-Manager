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
 return l
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,required=True);p.add_argument('--project',required=True);p.add_argument('--subnet',required=True);a=p.parse_args();prepare(a.directory,a.project,a.subnet);configure(a.directory);print('Four pinned Stage14 models copied read-only for Stage15, original models unchanged')

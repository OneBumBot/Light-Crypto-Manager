"""Historical files/projects are read only; keys are compared without emitting values."""
import argparse,json,subprocess,hashlib,gzip
from pathlib import Path
from datetime import datetime,timezone
from scripts.policy13_secret_match import SecretMatcher


def digest(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def historical():
    files={}
    for stage in range(8,13):
        for root in Path('.local-runtime').glob('stage'+str(stage)+'*'):
            for pattern in ['**/control.json','**/registry.json','**/*.password','**/*.key','**/*.db']:
                for f in root.glob(pattern):
                    if f.is_file():files[str(f)]=digest(f)
    archive=Path('.local-runtime/ground-truth-fix/archive-hashes.json');checked=0
    if archive.exists():
        for name,expected in json.loads(archive.read_text()).items():assert digest(name)==expected,name;checked+=1
    containers=[]
    ids=subprocess.check_output(['docker','ps','-a','-q'],text=True).split()
    if ids:
        for row in json.loads(subprocess.check_output(['docker','inspect',*ids],text=True)):
            project=row.get('Config',{}).get('Labels',{}).get('com.docker.compose.project','')
            if any(project.startswith('lcm-stage'+str(i)+'-') for i in range(8,13)):
                containers.append(dict(name=row['Name'],project=project,image=row['Image'],running=row['State']['Running'],started=row['State']['StartedAt'],finished=row['State']['FinishedAt']))
    volumes=[v for v in subprocess.check_output(['docker','volume','ls','--format','{{.Name}}'],text=True).splitlines() if any(v.startswith('lcm-stage'+str(i)+'-') for i in range(8,13))]
    return dict(private_inputs=files,archived_files_verified=checked,old_containers=sorted(containers,key=lambda v:v['name']),old_volumes=sorted(volumes))


def scan():
    values=[];keys=[];bad=[]
    roots=list(Path('.local-runtime/stage13').glob('*'))
    for root in roots:
        if not root.is_dir() or not (root/'control.json').exists():continue
        cfg=json.loads((root/'control.json').read_text())
        for item in cfg.values():keys.extend([item['registry']['key_hex'],*item['registry'].get('telemetry_keys',{}).values(),item['command_key'],item['status_key']])
        for f in root.rglob('*'):
            if f.is_dir() and f.stat().st_mode&0o077:bad.append(str(f))
            if f.is_file() and (f.suffix in ['.json','.env','.password','.key','.db'] or f.name=='compose.env'):
                if f.stat().st_mode&0o077:bad.append(str(f))
            if f.is_file() and f.suffix in ['.password','.key']:values.append(f.read_text().strip())
        for line in (root/'compose.env').read_text().splitlines():
            if '=' in line and any(v in line.split('=',1)[0] for v in ['PASSWORD','SECRET_KEY']):values.append(line.split('=',1)[1])
    assert len(keys)==len(set(keys)),'New key reuse'
    oldkeys=set()
    for stage in range(8,13):
        for f in Path('.local-runtime').glob('stage'+str(stage)+'*/**/control.json'):
            for item in json.loads(f.read_text()).values():
                if isinstance(item,dict) and 'registry' in item:oldkeys.update([item['registry']['key_hex'],*item['registry'].get('telemetry_keys',{}).values(),item['command_key'],item['status_key']])
    assert not set(keys)&oldkeys,'Historical key reuse'
    values+=keys
    for value in values[:]:values.extend(line for line in value.splitlines() if len(line)>=48 and not line.startswith('-'))
    needles=[v.encode() for v in set(values) if len(v)>=16];needles.extend(bytes.fromhex(k) for k in keys)
    names=set(subprocess.check_output(['git','ls-files'],text=True).splitlines());names.update(str(f) for f in Path('docs/reports/stage13').rglob('*') if f.is_file());leaks=[]
    with SecretMatcher(needles) as matcher:
        for name in names:
            f=Path(name)
            if not f.is_file():continue
            data=gzip.decompress(f.read_bytes()) if f.suffix=='.gz' else f.read_bytes()
            if matcher.contains(data):leaks.append(name)
    assert not bad and not leaks,'Private permission/report secret check failed'
    return dict(new_independent_keys=len(keys),historical_key_values_compared=len(oldkeys),key_reuse=False,private_permission_failures=[],secret_leaks=[],scanned_files=len(names))


def main():
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['before','after']);p.add_argument('--output',type=Path,required=True);p.add_argument('--before',type=Path);a=p.parse_args()
    if a.output.exists():p.error('Immutable report')
    state=historical()
    before=json.loads(Path('docs/reports/stage13/preservation-before.json').read_text())
    for name,expected in before['tracked'].items():assert digest(name)==expected,name
    # Frozen/holdout/model/PCAP paths are compared against original Git blobs too.
    baseline='649a80ff7f7d66f72f5f483b384754ae594f221e';extras=[]
    for name in subprocess.check_output(['git','ls-tree','-r','--name-only',baseline],text=True).splitlines():
        if any(s in name.lower() for s in ['frozen','holdout','pcap','dataset','model_registry']):
            if Path(name).is_file():assert Path(name).read_bytes()==subprocess.check_output(['git','show',baseline+':'+name]);extras.append(name)
    if a.phase=='after':
        original=json.loads(a.before.read_text())['historical'];assert state==original,'Historical private/project state changed'
        report=dict(historical=state,unchanged=True,**scan())
    else:report=dict(historical=state,private_snapshot_scope='Captured during task; old projects were not used; Git baseline and archive hashes are original pre-task authorities')
    report.update(phase=a.phase,observed_at=datetime.now(timezone.utc).isoformat(),source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),historical_tracked=len(before['tracked']),additional_frozen_paths=extras,main_sha=subprocess.check_output(['git','rev-parse','main'],text=True).strip(),exit_code=0)
    assert report['main_sha']=='c352d817386a17fb244d3567b287af0412eed4e4'
    a.output.write_text(json.dumps(report,indent=2));print('Historical hashes, private inputs and old project metadata checked; exit0')
if __name__=='__main__':main()

"""Preservation and isolated lab evidence, never emit secret values."""
import argparse,hashlib,json,gzip,subprocess
from pathlib import Path
from scripts.performance_lab import Lab


def main():
    p=argparse.ArgumentParser();p.add_argument('--directories',nargs='+',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():p.error('Immutable evidence exists')
    baseline=json.loads(Path('docs/reports/stage10/preservation-before.json').read_text());changed=[p for p,h in baseline.items() if not Path(p).is_file() or hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h]
    archive=Path('.local-runtime/ground-truth-fix/archive-hashes.json');archive_changed=[];archive_count=0
    if archive.exists():
        for path,expected in json.loads(archive.read_text()).items():
            archive_count+=1
            target=Path(path)
            if not target.exists():archive_changed.append(path);continue
            with target.open('rb') as f:actual=hashlib.file_digest(f,'sha256').hexdigest()
            if actual!=expected:archive_changed.append(path)
    assert not archive_changed, 'Historical local archive changed'
    labs=[];private_values=[];global_keys=[]
    for directory in a.directories:
        lab=Lab(directory);config=json.loads((lab.root/'control.json').read_text());keys=[];telemetry=[];bad_permissions=[]
        for device,cfg in config.items():
            keys.extend([cfg['command_key'],cfg['status_key']]);telemetry.extend([cfg['registry']['key_hex'],cfg['registry']['telemetry_keys']['AES-128-GCM']])
        private_values.extend(keys+telemetry);global_keys.extend(keys+telemetry)
        for f in lab.root.rglob('*'):
            if f.is_file() and (f.suffix in ['.password','.key'] or f.name in ['compose.env','control.json','device.db']):
                if f.stat().st_mode&0o077:bad_permissions.append(str(f.relative_to(lab.root)))
                if f.suffix in ['.password','.key']:
                    value=f.read_text().strip();private_values.append(value)
                    if f.suffix=='.key':private_values.extend(line for line in value.splitlines() if len(line)>=48 and not line.startswith('-'))
        for line in (lab.root/'compose.env').read_text().splitlines():
            if '=' in line and any(x in line.split('=',1)[0] for x in ['PASSWORD','SECRET_KEY']):private_values.append(line.split('=',1)[1])
        services=json.loads(lab.run('config','--format','json').stdout)['services']
        for name,s in services.items():
            if name in ['postgres','mongo','receiver','outbox-relay','web','broker','control-worker','policy-worker'] or name.startswith('device-'):
                assert s.get('cpus') and s.get('mem_limit') and s.get('logging'),name
        volumes=lab.run('config','--volumes').stdout.splitlines()
        assert len(keys)==len(set(keys)) and len(telemetry)==len(set(telemetry))
        labs.append(dict(project=lab.project,devices=len(config),control_keys_independent=True,telemetry_keys_independent=True,private_permissions_failures=bad_permissions,logical_volumes=volumes,limits_present=True))
    assert len(global_keys)==len(set(global_keys)), 'Cross-lab key reuse'
    files=subprocess.check_output(['git','ls-files'],text=True).splitlines()+[str(p) for p in Path('docs/reports/stage10').rglob('*') if p.is_file()]
    leaks=[]
    needles=[s.encode() for s in set(private_values) if len(s)>=16]
    for f in set(files):
        if not Path(f).is_file():continue
        data=Path(f).read_bytes()
        if f.endswith('.gz'):data=gzip.decompress(data)
        if any(s in data for s in needles):leaks.append(f)
    assert not changed and not leaks and not any(l['private_permissions_failures'] for l in labs)
    images=[]
    scan="import sys,json,hashlib;from pathlib import Path;needles=[v.encode() for v in json.load(sys.stdin) if len(v)>=16];files=[(p,p.read_bytes()) for p in Path('/app').rglob('*') if p.is_file()];print(json.dumps({'secret_found':any(any(s in data for s in needles) for p,data in files),'source_sha256':{str(p):hashlib.sha256(data).hexdigest() for p,data in files if p.suffix=='.py'}}))"
    for lab in labs:
        image=lab['project']+'-runtime'
        result=subprocess.run(['docker','run','--rm','-i','--cpus','0.5','--memory','256m','--network','none','--entrypoint','python',image,'-c',scan],input=json.dumps(private_values),capture_output=True,text=True,check=True,timeout=40)
        image_report=json.loads(result.stdout);assert not image_report['secret_found']
        image_report['image_id']=subprocess.check_output(['docker','image','inspect','--format','{{.Id}}',image],text=True).strip();images.append(image_report)
    report=dict(local_archive_files=archive_count,local_archive_changed=archive_changed,image_scans=images,preserved_historical_files=len(baseline),changed_historical_files=changed,secret_values_scanned=len(needles),secret_leak_paths=leaks,labs=labs,main_sha=subprocess.check_output(['git','rev-parse','main'],text=True).strip(),exit_code=0)
    a.output.write_text(json.dumps(report,indent=2));print(json.dumps({k:report[k] for k in ['preserved_historical_files','changed_historical_files','secret_leak_paths','exit_code']}))

if __name__=='__main__':main()

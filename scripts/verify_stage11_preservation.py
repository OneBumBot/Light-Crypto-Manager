"""Historical hashes, key isolation, image/API/log secret scan; never emit values."""
import argparse,hashlib,json,subprocess,gzip
from pathlib import Path
from scripts.kuz_lab import Lab


def main():
    p=argparse.ArgumentParser();p.add_argument('--directory',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():p.error('Immutable report exists')
    lab=Lab(a.directory);original='d226fbc56068caa5a2685d31a89eb0c85f8efe4c'
    paths=subprocess.check_output(['git','ls-tree','-r','--name-only',original,'docs/reports','migrations','src/web/ascon'],text=True).splitlines();changed=[]
    for name in paths:
        expected=subprocess.check_output(['git','show',original+':'+name])
        if not Path(name).is_file() or Path(name).read_bytes()!=expected:changed.append(name)
    archive=Path('.local-runtime/ground-truth-fix/archive-hashes.json');archive_changed=[];archive_count=0
    if archive.exists():
        for name,expected in json.loads(archive.read_text()).items():
            archive_count+=1;path=Path(name)
            if not path.is_file():archive_changed.append(name);continue
            with path.open('rb') as f:
                if hashlib.file_digest(f,'sha256').hexdigest()!=expected:archive_changed.append(name)
    config=json.loads((lab.root/'control.json').read_text());private=[];keys=[]
    for cfg in config.values():
        keys.extend([cfg['registry']['key_hex'],*cfg['registry'].get('telemetry_keys',{}).values(),cfg['command_key'],cfg['status_key']])
    assert len(keys)==len(set(keys))
    private.extend(keys);bad_permissions=[]
    for f in lab.root.rglob('*'):
        if f.is_dir() and f.stat().st_mode&0o077:bad_permissions.append(str(f.relative_to(lab.root)))
        if f.is_file() and (f.suffix in ['.password','.key'] or f.name in ['compose.env','control.json','device.db','registry.json']):
            if f.stat().st_mode&0o077:bad_permissions.append(str(f.relative_to(lab.root)))
            if f.suffix in ['.password','.key']:private.append(f.read_text().strip())
    for line in (lab.root/'compose.env').read_text().splitlines():
        if '=' in line and any(x in line.split('=',1)[0] for x in ['PASSWORD','SECRET_KEY']):private.append(line.split('=',1)[1])
    # PEM body lines are independently scanned too, including multiline/gzip logs.
    for value in private[:]:private.extend(line for line in value.splitlines() if len(line)>=48 and not line.startswith('-'))
    needles=[s.encode() for s in set(private) if len(s)>=16];leaks=[]
    files=set(subprocess.check_output(['git','ls-files'],text=True).splitlines())|{str(f) for f in Path('docs/reports/stage11').rglob('*') if f.is_file()}
    for name in files:
        path=Path(name)
        if not path.is_file():continue
        data=path.read_bytes()
        if path.suffix=='.gz':data=gzip.decompress(data)
        if any(s in data for s in needles):leaks.append(name)
    logs=lab.run('logs','--no-color').stdout
    assert not any(s.decode() in logs for s in needles)
    inspect=json.loads(subprocess.check_output(['docker','inspect',*lab.run('ps','-q').stdout.split()],text=True));containers=[]
    for c in inspect:
        h=c['HostConfig'];service=c['Config']['Labels']['com.docker.compose.service']
        assert h['Memory']>0 and h['NanoCpus']>0 and h['LogConfig']['Config'].get('max-size')
        assert all(n.startswith(lab.project+'_') for n in c['NetworkSettings']['Networks'])
        assert all(m['Name'].startswith(lab.project+'_') for m in c['Mounts'] if m['Type']=='volume')
        containers.append(dict(service=service,image_id=c['Image'],memory=h['Memory'],nano_cpus=h['NanoCpus'],restart_count=c['RestartCount']))
    scan="import sys,json;from pathlib import Path;n=[v.encode() for v in json.load(sys.stdin)];print(json.dumps({'secret_found':any(any(s in p.read_bytes() for s in n) for p in Path('/app').rglob('*') if p.is_file())}))"
    r=subprocess.run(['docker','run','--rm','-i','--network','none','--cpus','.5','--memory','256m','--entrypoint','python',lab.project+'-runtime','-c',scan],input=json.dumps(private),text=True,capture_output=True,check=True,timeout=40)
    image=json.loads(r.stdout);assert not image['secret_found']
    role=lab.run('exec','-T','web','python','-c',"import json;from pathlib import Path;r=json.loads(Path('/run/lcm/registry.json').read_text());assert all('Kuznyechik-MGM' not in e.get('telemetry_keys',{}) for e in r.values());assert not Path('/run/control/control.json').exists();print('web_has_no_mgm_or_control_keys')").stdout.strip()
    assert not changed and not archive_changed and not bad_permissions and not leaks
    main_sha=subprocess.check_output(['git','rev-parse','main'],text=True).strip();assert main_sha=='c352d817386a17fb244d3567b287af0412eed4e4'
    a.output.write_text(json.dumps(dict(project=lab.project,source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),historical_tracked_files=len(paths),changed_historical=changed,local_archive_files=archive_count,changed_archive=archive_changed,independent_keys=len(keys),private_permission_failures=bad_permissions,secret_leaks=leaks,image_scan=image,web_role_check=role,containers=containers,main_sha=main_sha,exit_code=0),indent=2))
    print('Historical hashes, private permissions, independent keys, image/log/Git scans: exit 0')

if __name__=='__main__':main()

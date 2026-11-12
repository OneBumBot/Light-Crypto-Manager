"""Offline final evidence inventory and secret scan; no state reset or service start."""
import argparse,gzip,hashlib,json,subprocess
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():p.error('Immutable report exists')
    root=Path('docs/reports/stage12');private=[]
    config=json.loads((a.directory/'control.json').read_text())
    for c in config.values():
        private.extend([c['registry']['key_hex'],*c['registry'].get('telemetry_keys',{}).values(),c['command_key'],c['status_key']])
    for f in a.directory.rglob('*'):
        if f.is_file() and f.suffix in ['.password','.key']:private.append(f.read_text().strip())
    for line in (a.directory/'compose.env').read_text().splitlines():
        if '=' in line and any(k in line.split('=',1)[0] for k in ['PASSWORD','SECRET_KEY']):private.append(line.split('=',1)[1])
    for v in private[:]:private.extend(s for s in v.splitlines() if len(s)>=48 and not s.startswith('-'))
    needles=[v.encode() for v in set(private) if len(v)>=16]
    names=set(subprocess.check_output(['git','ls-files'],text=True).splitlines())
    names.update(str(f) for f in root.rglob('*') if f.is_file())
    names.update(str(f) for f in Path('docs').glob('*.md') if f.is_file())
    leaks=[]
    for name in sorted(names):
        f=Path(name)
        if not f.is_file():continue
        data=f.read_bytes()
        if f.suffix=='.gz':data=gzip.decompress(data)
        if any(v in data for v in needles):leaks.append(name)
    assert not leaks, 'Secret scan failed; paths retained privately by caller'
    project=json.loads((a.directory/'stage12.json').read_text())['project']
    assert project.startswith('lcm-stage12-crypto-research-')
    running=subprocess.check_output(['docker','ps','--filter','label=com.docker.compose.project='+project,'--format','{{.Names}}'],text=True).splitlines()
    assert not running, 'Stop the lab with state retained before final inventory'
    baseline='20d298cc3b48f14920a00e9403bdaf0ff7e38c5a'
    historic=subprocess.check_output(['git','ls-tree','-r','--name-only',baseline,'docs/reports','migrations','src/web/ascon','third_party'],text=True).splitlines()
    for name in historic:assert Path(name).read_bytes()==subprocess.check_output(['git','show',baseline+':'+name]),'Historical content changed'
    artifacts=[]
    for f in sorted(root.rglob('*')):
        if not f.is_file() or f==a.output:continue
        recorded_source=None;recorded_exit=None
        if f.suffix=='.json':
            try:
                d=json.loads(f.read_text())
                if type(d) is dict:recorded_source=d.get('source_sha');recorded_exit=d.get('exit_code')
            except (UnicodeError,json.JSONDecodeError):pass
        artifacts.append(dict(path=str(f),bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest(),recorded_source_sha=recorded_source,recorded_exit_code=recorded_exit))
    source_files=subprocess.check_output(['git','diff','--name-only',baseline,'--','src','scripts','native','tests'],text=True).splitlines()
    code={name:hashlib.sha256(Path(name).read_bytes()).hexdigest() for name in source_files if Path(name).is_file()}
    main_sha=subprocess.check_output(['git','rev-parse','main'],text=True).strip();assert main_sha=='c352d817386a17fb244d3567b287af0412eed4e4'
    report=dict(source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),baseline_sha=baseline,runtime_validation_sha='bf8c7d5bfa84ed6120e0174c2b7500dc1da04af6',
        source_content_sha256=code,artifacts=artifacts,project=project,stage12_running_containers=running,historical_files_unchanged=len(historic),secret_scan_files=len(names),secret_leaks=[],main_sha=main_sha,
        provenance_limit='Null recorded source/exit means the raw artifact did not record it. See COMMANDS.md and validation content hashes; no historical SHA invented. Derived selections are not independent runs.',exit_code=0)
    a.output.write_text(json.dumps(report,indent=2));print(json.dumps(dict(artifacts=len(artifacts),secret_scan_files=len(names),historical_files=len(historic),running_stage12_containers=0,exit_code=0)))

if __name__=='__main__':main()

"""Bounded release security audit. No secret bytes/values exported."""
import argparse
import base64
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
from unittest.mock import patch
from scripts.policy13_secret_match import SecretMatcher
from scripts.stage16_demo import Demo
from src.shadow_ids.models import frozen

BASE='b2317f94b9198b6300d49d9e5effd11a7efee298'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def command(*args):return subprocess.check_output(list(args),text=True,timeout=60)


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():p.error('Immutable report exists')
    root=Path('.local-runtime/stage16');telemetry=[];control=[];needles=set();realms=[]
    def add(value):
        needles.add(value)
        needles.add(base64.b64encode(value))
    for directory in root.iterdir():
        registry=directory/'mqtt/registry.json'
        if not registry.exists():continue
        realms.append(directory.name)
        for row in json.loads(registry.read_text()).values():
            for key in [row['key_hex'],*row.get('telemetry_keys',{}).values()]:
                telemetry.append(key);add(key.encode());add(bytes.fromhex(key))
        if (directory/'control.json').exists():
            for row in json.loads((directory/'control.json').read_text()).values():
                for name in ['command_key','status_key']:
                    control.append(row[name]);add(row[name].encode());add(bytes.fromhex(row[name]))
            demo=Demo(directory);demo.check_material();demo.check_volumes()
        for folder in ['mqtt','mongo','accounts','alpha','beta','gamma']:
            scope=directory/folder
            if not scope.exists():continue
            for f in [scope,*scope.rglob('*')]:
                assert not f.stat().st_mode&0o077,'Private permission failure (values withheld)'
                if f.is_file() and f.suffix in ['.key','.password']:
                    value=f.read_bytes().strip();add(value)
                    for line in value.splitlines():
                        if len(line)>=48 and not line.startswith(b'-'):add(line)
        for line in (directory/'compose.env').read_text().splitlines():
            if '=' in line and any(key in line.split('=',1)[0] for key in ['PASSWORD','SECRET_KEY']):add(line.split('=',1)[1].encode())
    assert len(telemetry+control)==len(set(telemetry+control)),'New cross-device/algorithm/control key reuse'
    old=set()
    for f in Path('.local-runtime').rglob('registry.json'):
        if root in f.parents:continue
        try:
            for row in json.loads(f.read_text()).values():
                if isinstance(row,dict):old.update(v for v in [row.get('key_hex'),*row.get('telemetry_keys',{}).values()] if isinstance(v,str))
        except (ValueError,AttributeError):continue
    for f in Path('.local-runtime').rglob('control.json'):
        if root in f.parents:continue
        try:
            for row in json.loads(f.read_text()).values():
                if isinstance(row,dict):old.update(row[k] for k in ['command_key','status_key'] if k in row)
        except (ValueError,AttributeError):continue
    assert not set(telemetry+control)&old,'New key matches historical key'
    ids=command('docker','ps','-aq').split();allrows=json.loads(command('docker','inspect',*ids)) if ids else []
    rows=[r for r in allrows if (r['Config'].get('Labels') or {}).get('com.docker.compose.project','').startswith('lcm-stage16-final-demo-')]
    assert not any(r['State']['Running'] for r in rows),'New Stage16 services still running'
    infrastructure=[]
    historical_volumes=set(json.loads(Path('docs/reports/stage16/preservation-before.json').read_text())['snapshot']['old_volumes'])
    for row in rows:
        h=row['HostConfig'];project=row['Config']['Labels']['com.docker.compose.project'];mounts=row['Mounts']
        assert not h['Privileged'] and not any(m['Source'].endswith('/docker.sock') for m in mounts)
        for mount in mounts:
            if mount['Type']!='volume' or mount.get('Name','').startswith(project+'_'):continue
            name=mount['Name'];service=row['Config']['Labels'].get('com.docker.compose.service')
            assert (service,mount['Destination']) in [('mongo','/data/configdb'),('broker','/mosquitto/log')]
            assert name not in historical_volumes,'Historical auxiliary volume reused'
            owners={(r['Config'].get('Labels') or {}).get('com.docker.compose.project') for r in allrows if any(m.get('Name')==name for m in r['Mounts'])}
            assert owners=={project},'Auxiliary shared across projects'
        for binding in (h.get('PortBindings') or {}).values():
            assert all(v['HostIp']=='127.0.0.1' for v in binding)
        assert row['Config']['Labels'].get('com.docker.compose.service') not in ['shadow-network-observer','shadow-model-worker','ml-worker']
        infrastructure.append(dict(name=row['Name'],project=project,service=row['Config']['Labels'].get('com.docker.compose.service'),image_id=row['Image'],exit_code=row['State']['ExitCode'],running=False,cpu_nanos=h['NanoCpus'],memory_bytes=h['Memory'],log_config=h['LogConfig'],privileged=False,environment_names=[v.split('=',1)[0] for v in row['Config']['Env']],mount_targets=[dict(target=m['Destination'],read_only=not m['RW']) for m in mounts]))
    files=set(command('git','ls-files').splitlines())
    files.update(str(f) for f in Path('docs/reports/stage16').rglob('*') if f.is_file())
    files.update(str(f) for f in Path('docs').glob('STAGE16*.md'))
    files.update(str(f) for f in Path('scripts').glob('stage16*.py'))
    files.update(str(f) for f in Path('docs/diagrams/stage16').glob('*'))
    leaks=[];log_count=0;images=[]
    with SecretMatcher(v for v in needles if len(v)>=16) as matcher:
        for name in sorted(files):
            f=Path(name)
            if not f.is_file():continue
            value=f.read_bytes();value=gzip.decompress(value) if f.suffix=='.gz' else value
            if matcher.contains(value):leaks.append(name)
        for row in rows:
            r=subprocess.run(['docker','logs','--tail','1000',row['Id']],capture_output=True,timeout=30);log_count+=1
            if matcher.contains(r.stdout+r.stderr):leaks.append('new-container-log:'+row['Name'])
        image_ids=sorted({r['Image'] for r in rows if r['Config']['Labels'].get('com.docker.compose.service') in ['receiver','tests','device-alpha','web','control-worker']})
        for image in image_ids:
            cid=command('docker','create',image).strip()
            try:
                copied=subprocess.run(['docker','cp',cid+':/app','-'],capture_output=True,timeout=90);assert copied.returncode==0
                if matcher.contains(copied.stdout):leaks.append('application-image:'+image)
                with tarfile.open(fileobj=io.BytesIO(copied.stdout)) as archive:
                    prohibited=[m.name for m in archive.getmembers() if m.isfile() and Path(m.name).suffix in ['.pcap','.pcapng','.joblib','.skops','.password','.key','.db']]
                    assert not prohibited,'Private artifact file in application image'
                images.append(dict(image_id=image,generated_secret_matches=False,private_pcap_model_key_database_files=False,scope='/app archive only'))
            finally:subprocess.run(['docker','rm',cid],check=True,stdout=subprocess.DEVNULL)
    assert not leaks,'Generated secret match; actual values withheld'
    original=json.loads(Path('docs/reports/stage15/model-audit.json').read_text())
    assert sha('.local-runtime/stage14/study/experiment/test.json')==original['original_test_sha256']
    assert sha('.local-runtime/stage14/study/experiment/final-test-started')==original['original_holdout_marker_sha256']
    models=[]
    for role,pin in frozen().items():
        directory=Path('.local-runtime/stage14/study/models')/pin['model_id']/pin['model_version']
        assert sha(directory/'model.joblib')==pin['artifact_sha256'] and sha(directory/'manifest.json')==pin['manifest_sha256']
        assert not directory.stat().st_mode&0o077 and not (directory/'model.joblib').stat().st_mode&0o077
        models.append(dict(role=role,model_id=pin['model_id'],artifact_sha256=pin['artifact_sha256'],unchanged=True))
    critical=json.loads(Path('docs/reports/stage16/critical-source-baseline.json').read_text())['files']
    for name,row in critical.items():assert sha(name)==row['baseline_sha256'],name
    from src.kuz_release import validation_enabled
    from src.kuz_provider import operation,ProviderUnavailable
    from src.crypto_profiles import BY_ALGORITHM
    with patch.dict(os.environ,APP_ENV='test',LCM_KUZ_VALIDATION_AUTHORIZATION='1',LCM_LAB_PROJECT='lcm-stage16-final-demo-main'):
        assert not validation_enabled(),'Stage16 must not bypass existing Kuz release gate'
    with patch.dict(os.environ,LCM_KUZ_BACKEND='deliberately-unknown'):
        try:operation(1,bytes(32),bytes(16),b'a',b'x')
        except ProviderUnavailable:pass
        else:raise AssertionError('Unknown backend fallback')
    assert 'Magma-MGM' not in BY_ALGORITHM
    a.output.write_text(json.dumps(dict(source_sha=command('git','rev-parse','HEAD').strip(),fresh_realms=realms,independent_telemetry_keys=len(telemetry),independent_hmac_keys=len(control),historical_key_values_compared=len(old),reuse=False,secret_matches=[],files_scanned=len(files),new_container_log_tails_scanned=log_count,log_scope='Last1000lines per retained new container, not every historical log byte',application_images=images,infrastructure=infrastructure,old_stage14_models=models,old_holdout_and_marker_unchanged=True,critical_crypto_policy_source_and_migrations_unchanged=True,kuz_stage16_activation_refused=True,unknown_backend_no_fallback=True,magma_not_live=True,optional_shadow_unavailable_honest=True,all_new_services_stopped=True,fit_or_threshold_changes=0,exit_code=0),indent=2));print('Final exact-secret, role isolation, model freeze and source checks passed; exit0')

if __name__=='__main__':main()

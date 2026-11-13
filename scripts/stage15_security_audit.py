"""Exact secret/isolation audit. Only sanitized metadata, never private values."""
import argparse,gzip,hashlib,json,subprocess
from pathlib import Path
from scripts.policy13_secret_match import SecretMatcher
from src.shadow_ids.models import frozen
from src.classifier.ml.artifacts import verify,versions

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():p.error('Immutable audit')
 root=Path('.local-runtime/stage15');keys=[];needles=set();realms=[];permission=[]
 for directory in root.iterdir():
  registry=directory/'mqtt/registry.json'
  if not registry.exists():continue
  realms.append(directory.name)
  for r in json.loads(registry.read_text()).values():
   for k in [r['key_hex'],*r.get('telemetry_keys',{}).values()]:keys.append(k);needles.update([k.encode(),bytes.fromhex(k)])
  for folder in ['mqtt','mongo','models','accounts']:
   scope=directory/folder
   if scope.exists():
    for f in [scope,*scope.rglob('*')]:
     if f.stat().st_mode&0o077:permission.append(str(f))
     if f.is_file() and f.suffix in ['.key','.password']:
      value=f.read_bytes().strip();needles.add(value);needles.update(line for line in value.splitlines() if len(line)>=48 and not line.startswith(b'-'))
  for line in (directory/'compose.env').read_text().splitlines():
   if '=' in line and any(v in line.split('=',1)[0] for v in ['PASSWORD','SECRET_KEY']):needles.add(line.split('=',1)[1].encode())
 assert len(keys)==len(set(keys)),'New identity key reuse'
 old=set()
 for f in Path('.local-runtime').rglob('registry.json'):
  if root in f.parents:continue
  try:
   for r in json.loads(f.read_text()).values():
    if isinstance(r,dict):old.update(k for k in [r.get('key_hex'),*r.get('telemetry_keys',{}).values()] if isinstance(k,str) and k)
  except (ValueError,AttributeError):continue
 assert not set(keys)&old and not permission,'Key separation/private model/key permissions'
 ids=subprocess.check_output(['docker','ps','-aq'],text=True).split();allrows=json.loads(subprocess.check_output(['docker','inspect',*ids],text=True)) if ids else []
 rows=[r for r in allrows if (r['Config'].get('Labels') or {}).get('com.docker.compose.project','').startswith('lcm-stage15-shadow-ids-')];assert not any(r['State']['Running'] for r in rows),'Stage15 still running'
 shadows=[]
 for r in rows:
  service=r['Config']['Labels'].get('com.docker.compose.service','')
  if service not in ['shadow-network-observer','shadow-model-worker']:continue
  host=r['HostConfig'];mounts=r['Mounts'];env_names=[v.split('=',1)[0] for v in r['Config']['Env']];caps=[c.removeprefix('CAP_') for c in (host.get('CapAdd') or [])]
  assert not host['Privileged'] and not host.get('PortBindings') and host['CapDrop']==['ALL'] and not host.get('PidMode')
  assert not any(v in env_names for v in ['DATABASE_URL','CONTROL_KEYS_FILE','DEVICE_REGISTRY_FILE','MQTT_PASSWORD_FILE','MONGO_PASSWORD_FILE'])
  assert not any(any(s in str(v) for s in ['docker.sock','registry.json','control.json','receiver-security','control-security','/mqtt']) for v in mounts)
  if service=='shadow-model-worker':assert host['NetworkMode']=='none' and not caps
  else:assert caps==['NET_RAW'] and host['NetworkMode'].startswith('container:')
  shadows.append(dict(name=r['Name'],service=service,image_id=r['Image'],network_mode=host['NetworkMode'],capabilities=caps,private_credentials_mounted=False,environment_names=env_names,mount_targets=[dict(target=m['Destination'],read_only=not m['RW']) for m in mounts],read_only_root=host['ReadonlyRootfs']))
 files=set(subprocess.check_output(['git','ls-files'],text=True).splitlines());files.update(str(f) for f in Path('docs/reports/stage15').rglob('*') if f.is_file());files.update(str(f) for f in Path('docs').glob('STAGE15*.md'));files.update(str(f) for f in Path('scripts').glob('stage15*.py'));leaks=[];logs=0;images=0
 with SecretMatcher(v for v in needles if len(v)>=16) as matcher:
  for name in sorted(files):
   f=Path(name)
   if f.is_file():
    data=gzip.decompress(f.read_bytes()) if f.suffix=='.gz' else f.read_bytes()
    if matcher.contains(data):leaks.append(name)
  for r in rows:
   data=subprocess.run(['docker','logs','--tail','1000',r['Id']],capture_output=True,timeout=30);logs+=1
   if matcher.contains(data.stdout+data.stderr):leaks.append('container-log:'+r['Name'])
  for image in sorted({r['Image'] for r in rows if r['Config']['Labels'].get('com.docker.compose.service') in ['receiver','tests','lab-devices','shadow-network-observer','shadow-model-worker']}):
   cid=subprocess.check_output(['docker','create',image],text=True).strip()
   try:
    result=subprocess.run(['docker','cp',cid+':/app','-'],capture_output=True,timeout=60);assert result.returncode==0
    if matcher.contains(result.stdout):leaks.append('application-image:'+image)
    images+=1
   finally:subprocess.run(['docker','rm',cid],stdout=subprocess.DEVNULL,check=True)
 assert not leaks,'Generated secret exact match; values withheld'
 model_rows=[]
 for role,pin in frozen().items():
  meta,path=verify('.local-runtime/stage15/online/models',pin['model_id'],pin['model_version']);oldpath=Path('.local-runtime/stage14/study/models')/pin['model_id']/pin['model_version'];assert sha(path/'model.joblib')==sha(oldpath/'model.joblib')==pin['artifact_sha256'] and sha(path/'manifest.json')==pin['manifest_sha256'];model_rows.append(dict(role=role,model_id=pin['model_id'],artifact_sha256=pin['artifact_sha256'],original_unchanged=True))
 original=json.load(open('docs/reports/stage15/model-audit.json'));assert sha('.local-runtime/stage14/study/experiment/test.json')==original['original_test_sha256'];assert sha('.local-runtime/stage14/study/experiment/final-test-started')==original['original_holdout_marker_sha256']
 protected=['src/crypto_profiles.py','src/telemetry.py','src/ingestion.py','src/outbox.py','src/mongo_repository.py','src/kuz_provider.py','src/kuz_release.py','src/kuz_usage.py','src/device_control/agent.py','src/device_control/server.py','src/device_control/state.py','src/policy/worker.py','src/policy/state.py','src/policy/engine.py','src/ml_storage.py','src/ml_signals.py','src/research_stand/pcap_audit.py','src/research_stand/labels_v2.py','src/research_stand/label_verification.py']
 for name in protected:assert Path(name).read_bytes()==subprocess.check_output(['git','show','6903802:'+name]),name
 a.output.write_text(json.dumps(dict(source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),fresh_realms=len(realms),independent_telemetry_keys=len(keys),old_key_values_compared=len(old),key_reuse=False,secret_leaks=[],permission_failures=[],files_scanned=len(files),container_log_tails_scanned=logs,log_scope='Last1000lines/container; not every historical log byte',application_images_scanned=images,shadow_isolation=shadows,models=model_rows,old_holdout_and_marker_unchanged=True,cryptography_control_policy_oracle_byte_equal=protected,journal_group_read_exception='Journal-only750directory/640SQLite; role web supplementary group, read-only mount. RawPCAP/model/key files not shared.',all_stage15_services_stopped=True,exit_code=0),indent=2));print('Exact secret scan, original models/holdout, isolated capabilities and unchanged crypto/Policy/oracle verified; exit0')
if __name__=='__main__':main()

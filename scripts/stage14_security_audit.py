"""Read-only isolation and exact secret scan; private values never emitted."""
import argparse,json,subprocess,hashlib,gzip
from pathlib import Path
from scripts.policy13_secret_match import SecretMatcher

def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():p.error('Immutable report')
 root=Path('.local-runtime/stage14');keys=[];needles=set();bad=[];realms=[]
 for folder in root.iterdir():
  registry=folder/'mqtt/registry.json'
  if not registry.exists():continue
  realms.append(folder.name)
  for record in json.loads(registry.read_text()).values():
   for key in [record['key_hex'],*record.get('telemetry_keys',{}).values()]:keys.append(key);needles.update([key.encode(),bytes.fromhex(key)])
  for f in folder.rglob('*'):
   if f.stat().st_mode&0o077:bad.append(str(f))
   if f.is_file() and f.suffix in ['.key','.password']:
    value=f.read_bytes().strip();needles.add(value)
    needles.update(line for line in value.splitlines() if len(line)>=48 and not line.startswith(b'-'))
  for line in (folder/'compose.env').read_text().splitlines():
   if '=' in line and any(x in line.split('=',1)[0] for x in ['PASSWORD','SECRET_KEY']):needles.add(line.split('=',1)[1].encode())
 assert len(keys)==len(set(keys)),'Independent realm/device key reuse'
 old=set()
 for f in Path('.local-runtime').rglob('registry.json'):
  if root in f.parents:continue
  try:
   for r in json.loads(f.read_text()).values():
    if isinstance(r,dict):old.update([r.get('key_hex',''),*r.get('telemetry_keys',{}).values()])
  except (ValueError,AttributeError):continue
 assert not set(keys)&old,'Historical telemetry key reused'
 files=set(subprocess.check_output(['git','ls-files'],text=True).splitlines());files.update(str(f) for f in Path('docs/reports/stage14').rglob('*') if f.is_file());files.update(str(f) for f in Path('scripts').glob('stage14*'))
 leaks=[];image_count=0;log_count=0
 ids=subprocess.check_output(['docker','ps','-aq','--filter','label=com.docker.compose.project'],text=True).split();rows=json.loads(subprocess.check_output(['docker','inspect',*ids],text=True)) if ids else []
 rows=[r for r in rows if r['Config']['Labels'].get('com.docker.compose.project','').startswith('lcm-stage14-ground-truth-')]
 assert not any(r['State']['Running'] for r in rows),'Stage14 services still running'
 assert not any(r['HostConfig'].get('PortBindings') for r in rows),'Stage14 exposed host ports'
 with SecretMatcher(v for v in needles if len(v)>=16) as matcher:
  for name in sorted(files):
   f=Path(name)
   if f.is_file():
    data=gzip.decompress(f.read_bytes()) if f.suffix=='.gz' else f.read_bytes()
    if matcher.contains(data):leaks.append(name)
  for r in rows:
   output=subprocess.run(['docker','logs','--tail','1000',r['Id']],capture_output=True,timeout=30);log_count+=1
   if matcher.contains(output.stdout+output.stderr):leaks.append('container-log:'+r['Name'])
  # Image /app exports contain application source only; private runtime volumes are not exported.
  for image in sorted({r['Image'] for r in rows if any(x in r['Config']['Labels'].get('com.docker.compose.service','') for x in ['receiver','tests','lab-devices'])}):
   cid=subprocess.check_output(['docker','create',image],text=True).strip()
   try:
    result=subprocess.run(['docker','cp',cid+':/app','-'],capture_output=True,timeout=60)
    assert result.returncode==0,'Image source export failed'
    if matcher.contains(result.stdout):leaks.append('application-image:'+image)
    image_count+=1
   finally:subprocess.run(['docker','rm',cid],stdout=subprocess.DEVNULL,check=True)
 assert not leaks and not bad,'Secret/permission audit failed; values withheld'
 # Byte equality protects the actual cryptographic/control/Policy machinery.
 paths=['src/crypto_profiles.py','src/telemetry.py','src/ingestion.py','src/outbox.py','src/kuz_provider.py','src/kuz_usage.py','src/policy/worker.py','src/policy/state.py','src/policy/engine.py','src/device_control/agent.py','src/device_control/server.py','src/device_control/state.py']
 for name in paths:assert Path(name).read_bytes()==subprocess.check_output(['git','show','21a99bbc:'+name]),name
 report=dict(source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),realms=len(realms),new_independent_telemetry_keys=len(keys),old_key_values_compared=len(old),key_reuse=False,private_permission_failures=[],secret_leaks=[],files_scanned=len(files),container_logs_scanned=log_count,log_scope='Last1000 lines/container, not a claim about every historical log',application_images_scanned=image_count,crypto_control_policy_files_byte_equal_baseline=paths,all_stage14_services_stopped=True,no_host_ports=True,exit_code=0)
 a.output.write_text(json.dumps(report,indent=2));print('Isolation, key separation, exact secret matching and unchanged crypto/Policy checked; exit0')
if __name__=='__main__':main()

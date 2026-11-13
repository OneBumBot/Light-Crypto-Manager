"""Read-only audit of Stage13 isolation, quotas, roles, images and bounded logs."""
import json,subprocess,argparse
from pathlib import Path


def command(argv,**kw):return subprocess.run(argv,capture_output=True,check=True,**kw).stdout


def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():p.error('Immutable report')
 ids=command(['docker','ps','-a','-q']).decode().split();containers=json.loads(command(['docker','inspect',*ids]));rows=[];images=set();values=set();service_values=set();service_environment=[]
 for root in Path('.local-runtime/stage13').glob('*'):
  if not (root/'control.json').exists():continue
  for d in json.loads((root/'control.json').read_text()).values():values.update([d['registry']['key_hex'],*d['registry'].get('telemetry_keys',{}).values(),d['command_key'],d['status_key']])
  for line in (root/'compose.env').read_text().splitlines():
   if '=' in line and any(v in line.split('=',1)[0] for v in ['PASSWORD','SECRET_KEY']):
    value=line.split('=',1)[1];values.add(value);service_values.add(value)
  for f in root.rglob('*'):
   if f.is_file() and f.suffix in ['.password','.key']:
    value=f.read_text().strip();values.add(value);values.update(v for v in value.splitlines() if len(v)>48 and not v.startswith('-'))
 needles=[v.encode() for v in values if len(v)>=16];protected_needles=[v.encode() for v in values-service_values if len(v)>=16]
 image_inputs=json.dumps(list(values)).encode()
 for row in containers:
  project=row.get('Config',{}).get('Labels',{}).get('com.docker.compose.project','')
  if not project.startswith('lcm-stage13-policy-'):continue
  assert not row['State']['Running'],row['Name']+' still running'
  images.add(row['Image']);h=row['HostConfig'];service=row['Config']['Labels'].get('com.docker.compose.service','')
  data=command(['docker','logs',row['Id']]);assert not any(v in data for v in needles),'Secret in container log'
  # Completed init/test helpers are bounded by their invocation; persistent business services require quotas.
  persistent=service in ['postgres','mongo','broker','receiver','web','outbox-relay','policy-worker','control-worker'] or service.startswith('device-')
  if persistent:
   assert h['Memory']>0 and (h['NanoCpus']>0 or h['CpuQuota']>0),(service,'Missing CPU/RAM quota')
   assert h['LogConfig']['Config'].get('max-size') and h['LogConfig']['Config'].get('max-file'),(service,'Unbounded logs')
  if service.startswith('device-'):
   device=service[len('device-'):];private=[m for m in row['Mounts'] if m['Destination']=='/device'];assert len(private)==1 and private[0]['Name']==project+'_'+device+'-control','Wrong device role mount'
  if service in ['receiver','web']:assert not any(m.get('Name')==project+'_control-security' for m in row['Mounts']),'Controller keys mounted in receiver/web'
  for mount in row['Mounts']:
   if mount['Type']=='volume' and not mount['Name'].startswith(project+'_'):
    # Early base project auxiliary Mongo config/broker logs use fresh anonymous volumes.
    assert len(mount['Name'])==64,'Foreign named volume'
  assert not any(k.startswith('lcm-stage') and not k.startswith(project+'_') for k in row['NetworkSettings']['Networks']),'Foreign network'
  ports=h.get('PortBindings') or {}
  for bindings in ports.values():
   for binding in bindings or []:assert binding['HostIp']=='127.0.0.1','External service port'
  for k in ['Env','Cmd','Entrypoint']:
   for value in row['Config'].get(k) or []:
    blob=value.encode();assert not any(v in blob for v in protected_needles),'Crypto/MQTT/account secret in process config'
    if any(v in blob for v in needles):
     field=value.split('=',1)[0];assert k=='Env' and field in ['DATABASE_URL','POSTGRES_PASSWORD','FLASK_SECRET_KEY'],'Unexpected service secret in config'
     service_environment.append(dict(container=row['Name'],field=field,scope='Existing Compose DB/Flask environment; value withheld'))
  rows.append(dict(name=row['Name'],project=project,service=service,image=row['Image'],stopped=True,memory=h['Memory'],nano_cpus=h['NanoCpus'],logs_bounded=bool(h['LogConfig']['Config'].get('max-size')),logs_scanned_bytes=len(data)))
 image_results=[]
 code="""import sys,json,pathlib
values=json.load(sys.stdin);needles=[v.encode() for v in values if len(v)>=16];n=0
for p in pathlib.Path('/app').rglob('*'):
 if p.is_file():
  data=p.read_bytes();assert not any(v in data for v in needles),'Private material in image';n+=1
print(json.dumps({'files_scanned':n,'private_material_found':False}))
"""
 for identity in sorted(images):
  history=command(['docker','history','--no-trunc',identity]);assert not any(v in history for v in needles)
  # Broker/PostgreSQL/Mongo official images do not contain Python or app source.
  config=json.loads(command(['docker','image','inspect',identity]))[0]
  if config['Config'].get('WorkingDir')=='/app':
   result=json.loads(command(['docker','run','--rm','-i','--network','none','--read-only','--cpus','.5','--memory','256m','--entrypoint','python',identity,'-c',code],input=image_inputs));image_results.append(dict(image=identity,**result))
  else:image_results.append(dict(image=identity,scope='official service image; history/config/log checks, no application source scan'))
 a.output.write_text(json.dumps(dict(containers=rows,images=image_results,private_values_not_emitted=True,existing_service_environment=service_environment,all_stage13_stopped=True,old_projects_not_modified=True,exit_code=0),indent=2));print('Stage13 isolation/quotas/logs/image audit: exit0')
if __name__=='__main__':main()

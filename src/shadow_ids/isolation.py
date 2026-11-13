"""Deployment contract, not a claim that NET_RAW cannot transmit arbitrary raw bytes."""
def validate(services):
 capture=services['shadow-network-observer'];worker=services['shadow-model-worker']
 if capture.get('network_mode')!='service:lab-devices':raise ValueError('Unsafe capture namespace owner')
 if worker.get('network_mode')!='none':raise ValueError('Worker must have no network')
 for name,s in [('capture',capture),('model',worker)]:
  if s.get('privileged') or s.get('ports') or not s.get('read_only') or s.get('cap_drop')!=['ALL']:raise ValueError('Unsafe observer privileges')
  if any(k in s.get('environment',{}) for k in ['DATABASE_URL','CONTROL_KEYS_FILE','DEVICE_REGISTRY_FILE','MQTT_PASSWORD_FILE','MONGO_PASSWORD_FILE']):raise ValueError('Sensitive environment forbidden')
  for volume in s.get('volumes',[]):
   value=str(volume)
   if any(x in value for x in ['docker.sock','registry.json','control.json','receiver-security','control-security','mqtt/']):raise ValueError('Sensitive mount forbidden')
 if capture.get('cap_add')!=['NET_RAW'] or worker.get('cap_add'):raise ValueError('Capability scope')
 return True

def check_used_volumes(names,project,exists):
 if not isinstance(names,list) or not names:raise ValueError('Missing used-state manifest')
 for name in names:
  if type(name) is not str or not name.startswith(project+'_') or not exists(name):raise ValueError('Previously used volume unavailable; reviewed recovery/rekey required')
 return True

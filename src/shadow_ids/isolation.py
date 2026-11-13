"""Deployment contract, not a claim that NET_RAW cannot transmit arbitrary raw bytes."""
def validate(services):
 capture=services['shadow-network-observer'];worker=services['shadow-model-worker']
 if capture.get('network_mode')!='service:lab-devices':raise ValueError('Unsafe capture namespace owner')
 if worker.get('network_mode')!='none':raise ValueError('Worker must have no network')
 for name,s in [('capture',capture),('model',worker)]:
  if s.get('privileged') or s.get('ports') or not s.get('read_only') or s.get('cap_drop')!=['ALL']:raise ValueError('Unsafe observer privileges')
  for volume in s.get('volumes',[]):
   value=str(volume)
   if any(x in value for x in ['docker.sock','registry.json','control.json','receiver-security','control-security','mqtt/']):raise ValueError('Sensitive mount forbidden')
 if capture.get('cap_add')!=['NET_RAW'] or worker.get('cap_add'):raise ValueError('Capability scope')
 return True

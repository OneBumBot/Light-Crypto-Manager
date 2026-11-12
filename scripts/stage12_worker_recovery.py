"""Actual provider-process crashes in receiver and agent; no authority reset."""
import argparse,json,time
from pathlib import Path
from scripts.crypto_research_lab import Lab
from scripts.performance_run import login
from scripts.performance_reliability import switch,wait
from src.crypto_profiles import KUZ,ASCON


def main():
 p=argparse.ArgumentParser();p.add_argument('--directory',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():p.error('Immutable report')
 lab=Lab(a.directory);s,u,t=login(lab);events=[]
 switch(lab,s,u,t,'alpha',KUZ)
 def snapshot():return lab.probe('snapshot')
 def alpha(st):return st['per_device']['alpha']['count']
 kill="import os,signal;from pathlib import Path;ids=[]\nfor p in Path('/proc').iterdir():\n if not p.name.isdigit():continue\n try:a=(p/'cmdline').read_bytes().split(b'\\0')\n except (FileNotFoundError,PermissionError):continue\n if a and a[0].endswith(b'/lcm-kuz-mgm') and len(a)>1 and a[1]==b'--worker':ids.append(int(p.name))\nassert len(ids)==1, len(ids)\nos.kill(ids[0],signal.SIGKILL);print('provider_child_killed')"
 for service in ['receiver','device-alpha']:
  before=snapshot();time.sleep(1.1)
  result=lab.run('exec','-T',service,'python','-c',kill)
  after_kill=snapshot();after_kill_count=alpha(after_kill)
  if service=='device-alpha':
   time.sleep(2);lab.run('up','-d','--no-deps','--wait','device-alpha')
  end=time.monotonic()+30
  while time.monotonic()<end:
   after=snapshot()
   if alpha(after)>after_kill_count:break
   time.sleep(.5)
  else:
   # Infrastructure failure may stop explicit MQTT disconnect; operator restart is allowed, never fallback.
   lab.run('up','-d','--no-deps','--force-recreate','--wait',service);after=wait(lambda:(v if alpha(v:=snapshot())>after_kill_count else None),30)
  assert after['completed']==before['completed'] and next(d for d in after['devices'] if d['device_id']=='alpha')['effective_profile']==KUZ
  if service=='device-alpha':assert next(d for d in after['devices'] if d['device_id']=='alpha')['sequence_reserved']>next(d for d in before['devices'] if d['device_id']=='alpha')['sequence_reserved']
  events.append(dict(service=service,before=before,after_kill=after_kill,after=after,worker_kill=result.stdout.strip(),no_false_transition=True))
 switch(lab,s,u,t,'alpha',ASCON)
 a.output.write_text(json.dumps(dict(project=lab.project,events=events,commands=lab.commands,exit_code=0),indent=2));print('Real receiver/agent provider crashes recovered: exit0')

if __name__=='__main__':main()

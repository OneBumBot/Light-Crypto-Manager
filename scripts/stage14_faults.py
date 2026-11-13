"""Real scoped service/resource faults after collection; never a model dataset."""
import json,subprocess,time,argparse
from pathlib import Path
from datetime import datetime,timezone
from scripts.stage14_lab import Lab as Infrastructure
from src.research_stand.orchestrator import Lab
from src.research_stand.config import Experiment
from scripts.stage14_collect import check_source


def main():
 p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,default=Path('.local-runtime/stage14/pilot'));p.add_argument('--output',type=Path,default=Path('docs/reports/stage14/service-faults.json'));a=p.parse_args()
 if a.output.exists():p.error('Immutable report')
 infra=Infrastructure(a.directory);records=[];root=Path('.local-runtime/stage14/fault-captures');root.mkdir(exist_ok=True,mode=0o700)
 for i,kind in enumerate(['postgres','mongo','broker_logging','receiver_restart','tight_disk_watchdog','memory_cap','cpu_watchdog']):
  extra=[infra.root/'stage14.compose.json'];cid=infra.run('ps','-q','traffic-collector').stdout.strip();limited=False
  if kind=='broker_logging':
   override=infra.root/'no-broker-logging.yaml';override.write_text('services:\n  broker:\n    logging:\n      driver: none\n      options: !reset {}\n');override.chmod(0o600);extra.append(override);subprocess.run(infra.base+['-f',str(override),'up','-d','--no-deps','--force-recreate','--wait','broker'],check=True,capture_output=True);time.sleep(1)
  if kind in ['memory_cap','cpu_watchdog']:
   cmd=['docker','update','--memory','24m','--memory-swap','24m',cid] if kind=='memory_cap' else ['docker','update','--cpus','.01',cid]
   subprocess.run(cmd,check=True,capture_output=True);limited=True
  lab=Lab(infra.env,root,compose_overrides=extra);original=lab.resource_usage;calls=[0];measurement={};name='fault-'+kind.replace('_','-');started=time.time();status='complete';diagnostic=None
  def usage():
   value=original();calls[0]+=1
   if calls[0]==2:
    if kind in ['postgres','mongo']:infra.run('stop',kind)
    elif kind=='receiver_restart':infra.run('restart','receiver')
    elif kind=='tight_disk_watchdog':
     measurement.update(observed_research_bytes=value['lab-devices']['bytes'],intentionally_tightened_test_limit=1,actual_disk_full=False)
     if value['lab-devices']['bytes']>1:raise ValueError('Measured research bytes exceed intentionally tightened fault-test budget')
   return value
  lab.resource_usage=usage
  try:
   lab.experiment(Experiment(name,'regular',4,6,.45,.02,149000+i));check_source(root/name)
  except (ValueError,RuntimeError,KeyError,TypeError,OSError,subprocess.SubprocessError) as e:status='quarantined';diagnostic=type(e).__name__+':'+str(e)[:240]
  finally:
   if limited:
    subprocess.run(['docker','update','--memory','256m','--memory-swap','512m','--cpus','1',cid],check=True,capture_output=True);time.sleep(1)
   folder=root/name
   if not folder.exists():subprocess.run(['docker','cp',cid+':/research/'+name,str(folder)],capture_output=True,timeout=15)
   folder.mkdir(exist_ok=True,mode=0o700)
   if kind in ['postgres','mongo']:infra.run('up','-d','--no-deps','--wait',kind)
   if kind=='broker_logging':infra.run('up','-d','--no-deps','--force-recreate','--wait','broker')
   if limited:infra.run('up','-d','--no-deps','--force-recreate','traffic-collector')
  if kind!='receiver_restart':assert status=='quarantined',kind+' failed to quarantine source'
  # MQTT PUBACK is never treated as PG admission; drain after restoring original volumes.
  end=time.monotonic()+60;after=None
  while time.monotonic()<end:
   try:after=lab.state(time.time()-60)
   except (RuntimeError,ValueError):time.sleep(.5);continue
   if after['outbox_pending']==0:break
   time.sleep(.5)
  assert after and after['outbox_pending']==0
  events=[]
  if kind=='memory_cap':
   r=subprocess.run(['docker','events','--since',str(int(started)-2),'--until',str(int(time.time())+1),'--filter','container='+cid,'--filter','event=oom','--format','{{json .}}'],capture_output=True,text=True,timeout=10);events=[json.loads(v) for v in r.stdout.splitlines() if v.strip()]
  record=dict(case=kind,status=status,diagnostic=diagnostic,started_at=datetime.fromtimestamp(started,timezone.utc).isoformat(),finished_at=datetime.now(timezone.utc).isoformat(),duration_seconds=time.time()-started,measurements=measurement,docker_oom_events=len(events),raw_preserved_files=[f.name for f in folder.iterdir()],outbox_pending_after_restore=after['outbox_pending'],mongo_records_after_restore=after['mongo_records'],scientific_dataset_member=False)
  (folder/'fault-receipt.json').write_text(json.dumps(record,indent=2));records.append(record);print(kind,status,'preserved',len(record['raw_preserved_files']),'files',flush=True)
 a.output.write_text(json.dumps(dict(project=infra.project,records=records,all_original_volumes_retained=True,raw_sources_not_deleted=True,commands=infra.commands,exit_code=0),indent=2))
if __name__=='__main__':main()

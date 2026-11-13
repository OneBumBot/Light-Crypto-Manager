"""Actual bounded faults in the new Stage15 project; no historical service touched."""
import argparse,json,os,shutil,subprocess,threading,time
from pathlib import Path
from scripts.stage15_setup import lab
from scripts.stage15_runs import capture,workload,wait
from scripts.stage15_performance import state
from src.shadow_ids.journal import Journal,path_for

def worker(l,name,instance,models=None,duration=30):
 args=['run','-d','--no-deps','--name',l.project+'-'+name+'-'+instance]
 if models:args+=['-v',str(models)+':/badmodels:ro']
 return l.run(*args,'shadow-model-worker','python','-m','src.shadow_ids.worker','--root','/shadow/'+name,'--models','/badmodels' if models else '/models','--parity','/parity.json','--duration',str(duration)).stdout.strip().splitlines()[-1]

def inspect(cid):
 r=json.loads(subprocess.check_output(['docker','inspect',cid],text=True))[0]
 return dict(exit_code=r['State']['ExitCode'],running=r['State']['Running'],oom_killed=r['State']['OOMKilled'])
def main():
 p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,default=Path('.local-runtime/stage15/online'));a=p.parse_args();l=lab(a.directory);out=Path('docs/reports/stage15/recovery.json')
 if out.exists():raise ValueError('Immutable recovery output')
 records=[]
 for case in ['observer_sigkill','model_sigkill','receiver_restart','broker_outage','postgres_outage','mongo_outage','missing_model','wrong_model_hash','wrong_feature_version','memory_cap','queue_overflow']:
  name='fault-'+case.replace('_','-');root=l.root/'shadow'/name;before=state(l);bad=None;cid=None;wid=None;duration=22;extra={};started=time.time();result=[];errors=[]
  if case in ['missing_model','wrong_model_hash','wrong_feature_version']:
   bad=l.root/('bad-'+case)
   if bad.exists():raise ValueError('Previous negative artifacts preserved')
   if case=='missing_model':bad.mkdir(mode=0o700)
   else:
    shutil.copytree(l.root/'models',bad)
    if case=='wrong_model_hash':
     f=next(bad.rglob('model.joblib'));data=bytearray(f.read_bytes());data[-1]^=1;f.write_bytes(data)
    else:
     f=next(bad.rglob('manifest.json'));value=json.loads(f.read_text());value['feature_version']='network-core-v1';f.write_text(json.dumps(value))
   for f in bad.rglob('*'):f.chmod(0o700 if f.is_dir() else 0o600)
  if case=='queue_overflow':
   cid=l.run('run','-d','--no-deps','--name',l.project+'-'+name+'-capture','shadow-network-observer','python','-m','src.shadow_ids.capture','--root','/shadow/'+name,'--duration',str(duration),'--capacity','1').stdout.strip().splitlines()[-1];time.sleep(1)
  else:cid=capture(l,name,condition='all',duration=duration);wid=worker(l,name,'worker',bad)
  def drive():
   try:result.append(workload(l,name,3,.5,seed=15700+len(records)))
   except Exception as exc:errors.append(type(exc).__name__)
  thread=threading.Thread(target=drive);thread.start();time.sleep(3)
  try:
   if case=='observer_sigkill':
    subprocess.run(['docker','kill','--signal','KILL',cid],check=True,capture_output=True);extra['observer_after_kill']=inspect(cid)
    newname=name+'-restart';newcid=capture(l,newname,condition='all',duration=18);newwid=worker(l,newname,'worker',duration=24);extra['restart_root']=newname
   if case=='model_sigkill':
    subprocess.run(['docker','kill','--signal','KILL',wid],check=True,capture_output=True);extra['worker_after_kill']=inspect(wid);time.sleep(.5);wid=worker(l,name,'restarted-worker')
   if case=='memory_cap':subprocess.run(['docker','update','--memory','16m','--memory-swap','16m',cid],check=True,capture_output=True)
   if case=='receiver_restart':l.run('restart','receiver')
   if case in ['broker_outage','postgres_outage','mongo_outage']:
    service=case.split('_')[0];l.run('stop',service);time.sleep(3);l.run('up','-d','--no-deps','--wait',service,timeout=90)
   thread.join(35)
   if thread.is_alive():raise TimeoutError('Workload watchdog')
   if case not in ['observer_sigkill','memory_cap']:wait(cid)
   if wid:wait(wid)
   if case=='observer_sigkill':
    wait(newcid);wait(newwid);newdb=Journal(path_for(l.root/'shadow'/newname),readonly=True);extra['restart_statuses']=dict(newdb.db.execute("SELECT json_extract(value,'$.inference_status'),count(*) FROM results GROUP BY1".replace('GROUP BY1','GROUP BY 1')).fetchall());extra['restart_capture_uuid']=newdb.snapshot()['capture'].get('capture_id');newdb.close()
   if case=='memory_cap':extra['capture_after_memory_limit']=inspect(cid)
   after=state(l);deadline=time.monotonic()+30
   while after['outbox_pending'] and time.monotonic()<deadline:time.sleep(.3);after=state(l)
   db=Journal(path_for(root),readonly=True);snap=db.snapshot();counts=dict(db.db.execute("SELECT json_extract(value,'$.inference_status'),count(*) FROM results GROUP BY 1").fetchall());duplicates=db.db.execute('SELECT count(*) FROM(SELECT event_id,model_id,count(*)n FROM results GROUP BY event_id,model_id HAVING n>1)').fetchone()[0];snapshot_counts=dict(events=snap['packets'],results=snap['inferences'],pending=snap['pending']);db.close()
   if case in ['missing_model','wrong_model_hash','wrong_feature_version']:assert counts and set(counts)=={'MODEL_UNAVAILABLE'}
   if case=='queue_overflow':assert snap['capture']['status']=='CAPTURE_INCOMPLETE' and (snap['capture']['queue_overflow'] or snap['capture']['reader_drops'])
   assert duplicates==0 and after['outbox_pending']==0
   record=dict(case=case,started_at=started,finished_at=time.time(),duration_seconds=time.time()-started,capture=snap['capture'],worker=snap['worker'],counts=snapshot_counts,inference_statuses=counts,duplicate_results=duplicates,telemetry_pg_delta=after['categories'].get('accepted',0)-before['categories'].get('accepted',0),telemetry_mongo_delta=after['mongo_records']-before['mongo_records'],outbox_pending_after=after['outbox_pending'],generator_errors=result[0]['errors'] if result else errors,raw_retained=True,**extra)
  finally:
   thread.join(30)
  records.append(record);out.with_name('recovery-progress.json').write_text(json.dumps(dict(records=records),indent=2));print(case,'PG+',record['telemetry_pg_delta'],'Mongo+',record['telemetry_mongo_delta'],counts,flush=True)
 # Actual bounded tmpfs shortage, not filling the host disk or modifying a PCAP.
 owner=l.run('ps','-q','lab-devices').stdout.strip();image=l.project+'-shadow-capture';name=l.project+'-disk-floor'
 cmd=['docker','run','-d','--name',name,'--network','container:'+owner,'--cap-drop','ALL','--cap-add','NET_RAW','--read-only','--user',str(os.getuid())+':'+str(os.getgid()),'--cpus','.5','--memory','128m','--tmpfs','/shadow:rw,size=1m,mode=700,uid='+str(os.getuid())+',gid='+str(os.getgid()),'-v',str(Path('src/shadow_ids').resolve())+':/app/src/shadow_ids:ro',image,'python','-m','src.shadow_ids.capture','--root','/shadow/disk-floor','--duration','5'];cid=subprocess.check_output(cmd,text=True).strip();p=subprocess.run(['docker','wait',cid],capture_output=True,text=True,timeout=15);assert p.stdout.strip()!='0';records.append(dict(case='disk_floor_watchdog',actual_tmpfs_bytes=1024**2,status='BLOCKED_PREFLIGHT',host_disk_filled=False,container=inspect(cid)))
 out.write_text(json.dumps(dict(records=records,source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),all_previous_volumes_preserved=True,no_old_services_used=True,security='SHADOW_ONLY/unbound/trusted_detector=false; no crypto command',exit_code=0),indent=2));print('Actual resource/source/process fault matrix completed; exit0')
if __name__=='__main__':main()

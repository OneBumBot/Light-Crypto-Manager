"""Separate unprivileged model process; SQLite only, no MQTT/Policy/Control credentials."""
import argparse,hashlib,json,os,resource,time
from pathlib import Path
from .journal import Journal,path_for
from .models import frozen,load_models,scores

def process(db,loaded,rows,model_error=None):
 valid=[];start=time.time();pins=frozen();events=[]
 for row in rows:
  try:
   event=json.loads(row['packet'])
   if not isinstance(event,dict) or event.get('mode')!='SHADOW_ONLY' or event.get('trusted_detector') is not False or event.get('device_binding')!='unbound' or not all(k in event for k in ['event_id','ordinal','capture_id','capture_timestamp','feature_ready_at','observer_id','feature_version','status']):raise ValueError('Malformed shadow event')
  except (ValueError,TypeError):event=dict(event_id=row['id'],ordinal=row.get('ordinal',0),capture_id=row.get('run','unknown'),capture_timestamp=None,feature_ready_at=None,observer_id='unknown',feature_version='unknown',status='MALFORMED_EVENT',diagnostic='MalformedShadowEvent')
  source=db.db.execute("SELECT value FROM status WHERE name='capture'").fetchone()
  if source:
   current=json.loads(source[0])
   if current.get('status')=='CAPTURE_INCOMPLETE' or current.get('queue_overflow',0) or current.get('reader_drops',0):event['context_dropped']=True
  events.append(event)
 for e in events:
  if e['status']=='FEATURE_READY' and not e.get('context_dropped'):valid.append(e)
 try:values=scores(loaded,valid) if loaded and not model_error else {};error=model_error
 except Exception as exc:values={};error=type(exc).__name__
 ended=time.time();indices={e['event_id']:i for i,e in enumerate(valid)}
 pairs=[]
 for row,event in zip(rows,events):
  results=[]
  for role,(pin,_) in loaded.items() if loaded else [(r,(p,None)) for r,p in pins.items()]:
   status=event['status'];score=None
   if error:status='MODEL_UNAVAILABLE' if model_error else 'INFERENCE_ERROR'
   elif event.get('context_dropped'):status='CAPTURE_DROPPED'
   elif event['event_id'] in indices and role in values:status='SCORED';score=values[role][indices[event['event_id']]]
   result=dict(event_id=event['event_id'],capture_id=event['capture_id'],packet_identity=dict(ordinal=event['ordinal'],sha256=event.get('packet_sha256')),session_id=event['capture_id']+':'+event.get('session','unknown'),observer_id=event['observer_id'],feature_version=event['feature_version'],model_id=pin['model_id'],model_role=role,model_version=pin['model_version'],artifact_sha256=pin['artifact_sha256'],capture_timestamp=event['capture_timestamp'],feature_ready_at=event['feature_ready_at'],inference_start=start,inference_finish=ended,journal_ready_at=time.time(),score=score,threshold=pin['threshold'],comparison=(score>=pin['threshold']) if score is not None else None,inference_status=status,diagnostic=error or event.get('diagnostic'),source_availability='observed_packet',capture_validity='provisional_until_final_capture_stats',context_dropped=event.get('context_dropped',False),device_binding='unbound',mode='SHADOW_ONLY',trusted_detector=False)
   results.append(result)
  pairs.append((row,results))
 if pairs:db.complete_batch(pairs)
 for row,event in zip(rows,events):
  # This timestamp is taken only after SQLite commit returns; missing audit after
  # a crash is not replaced with a fabricated zero latency.
  with (db.path.parent/'commit-timings.jsonl').open('a') as stream:
   stream.write(json.dumps(dict(event_id=row['id'],capture_timestamp=event['capture_timestamp'],feature_ready_at=event['feature_ready_at'],inference_start=start,inference_finish=ended,journal_commit_ack_at=time.time()),allow_nan=False)+'\n')
 return len(rows)

def run(root,models,roles,duration,parity):
 if not 3<=duration<=120:raise ValueError('Worker duration bound')
 # Live inference cannot start from a user assertion of parity.
 report=json.loads(Path(parity).read_text())
 if report.get('parser_sha256')!=hashlib.sha256(Path(__file__).with_name('features.py').read_bytes()).hexdigest() or report.get('status')!='PASS' or report.get('feature_version')!='tcp-packet-passive-v1' or report.get('integral_mismatches')!=0 or report.get('delta_mismatches')!=0 or report.get('supported_packets',0)<100:raise ValueError('Feature parity gate blocked')
 db=Journal(path_for(root));db.status('parity',report);loaded={};error=None
 try:loaded=load_models(models,roles)
 except Exception as exc:error=type(exc).__name__;loaded={r:(frozen()[r],None) for r in roles}
 deadline=time.monotonic()+duration;processed=0;last_inference=None
 while time.monotonic()<deadline:
  rows=db.pending();processed+=process(db,loaded,rows,error) if rows else 0
  if rows:last_inference=time.time()
  db.status('worker',dict(status='MODEL_UNAVAILABLE' if error else 'READY',heartbeat=time.time(),processed=processed,storage_retries=db.retries,storage_commits=db.commits,last_inference=last_inference,model_roles=roles,model_error=error,user_cpu=resource.getrusage(resource.RUSAGE_SELF).ru_utime,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss))
  if (Path(root)/'capture-status.json').exists() and not db.pending():break
  if not rows:time.sleep(.05)
 from .sessions import aggregate
 state=db.snapshot()['capture'];final=bool(state.get('complete')) and not db.pending()
 (Path(root)/'sessions.json').write_text(json.dumps(dict(results=aggregate(db,final),complete_capture=final,finalized_at=time.time()),indent=2))
 db.close()
def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--models',type=Path,required=True);p.add_argument('--roles',nargs='+',default=['rf_binary','if','rf_session','if_session']);p.add_argument('--duration',type=float,default=50);p.add_argument('--parity',type=Path,required=True);a=p.parse_args();run(a.root,a.models,a.roles,a.duration,a.parity)
if __name__=='__main__':main()

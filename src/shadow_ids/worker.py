"""Separate unprivileged model process; SQLite only, no MQTT/Policy/Control credentials."""
import argparse,json,os,resource,time
from pathlib import Path
from .journal import Journal
from .models import frozen,load_models,scores

def process(db,loaded,rows,model_error=None):
 valid=[];start=time.time();pins=frozen();events=[json.loads(row['packet']) for row in rows]
 for e in events:
  if e['status']=='FEATURE_READY' and not e.get('context_dropped'):valid.append(e)
 try:values=scores(loaded,valid) if loaded else {};error=model_error
 except Exception as exc:values={};error=type(exc).__name__
 ended=time.time();indices={e['event_id']:i for i,e in enumerate(valid)}
 for row,event in zip(rows,events):
  results=[]
  for role,(pin,_) in loaded.items() if loaded else [(r,(p,None)) for r,p in pins.items()]:
   status=event['status'];score=None
   if error:status='MODEL_UNAVAILABLE' if model_error else 'INFERENCE_ERROR'
   elif event.get('context_dropped'):status='CAPTURE_DROPPED'
   elif event['event_id'] in indices and role in values:status='SCORED';score=values[role][indices[event['event_id']]]
   result=dict(event_id=event['event_id'],capture_id=event['capture_id'],packet_identity=dict(ordinal=event['ordinal'],sha256=event.get('packet_sha256')),session_id=event['capture_id']+':'+event.get('session','unknown'),observer_id=event['observer_id'],feature_version=event['feature_version'],model_id=pin['model_id'],model_role=role,model_version=pin['model_version'],artifact_sha256=pin['artifact_sha256'],capture_timestamp=event['capture_timestamp'],feature_ready_at=event['feature_ready_at'],inference_start=start,inference_finish=ended,journal_ready_at=time.time(),score=score,threshold=pin['threshold'],comparison=(score>=pin['threshold']) if score is not None else None,inference_status=status,diagnostic=error or event.get('diagnostic'),source_availability='observed_packet',context_dropped=event.get('context_dropped',False),device_binding='unbound',mode='SHADOW_ONLY',trusted_detector=False)
   results.append(result)
  db.complete(row,results)
 return len(rows)

def run(root,models,roles,duration,parity):
 if not 3<=duration<=120:raise ValueError('Worker duration bound')
 # Live inference cannot start from a user assertion of parity.
 report=json.loads(Path(parity).read_text())
 if report.get('status')!='PASS' or report.get('feature_version')!='tcp-packet-passive-v1' or report.get('integral_mismatches')!=0 or report.get('delta_mismatches')!=0 or report.get('supported_packets',0)<100:raise ValueError('Feature parity gate blocked')
 db=Journal(Path(root)/'shadow.db');db.status('parity',report);loaded={};error=None
 try:loaded=load_models(models,roles)
 except Exception as exc:error=type(exc).__name__
 deadline=time.monotonic()+duration;processed=0;last_inference=None
 while time.monotonic()<deadline:
  rows=db.pending();processed+=process(db,loaded,rows,error) if rows else 0
  if rows:last_inference=time.time()
  db.status('worker',dict(status='MODEL_UNAVAILABLE' if error else 'READY',heartbeat=time.time(),processed=processed,last_inference=last_inference,model_roles=roles,model_error=error,user_cpu=resource.getrusage(resource.RUSAGE_SELF).ru_utime,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss))
  if (Path(root)/'capture-status.json').exists() and not db.pending():break
  if not rows:time.sleep(.05)
 from .sessions import aggregate
 state=db.snapshot()['capture'];final=bool(state.get('complete')) and not db.pending()
 (Path(root)/'sessions.json').write_text(json.dumps(dict(results=aggregate(db,final),complete_capture=final,finalized_at=time.time()),indent=2))
 db.close()
def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--models',type=Path,required=True);p.add_argument('--roles',nargs='+',default=['rf_binary','if','rf_session','if_session']);p.add_argument('--duration',type=float,default=50);p.add_argument('--parity',type=Path,required=True);a=p.parse_args();run(a.root,a.models,a.roles,a.duration,a.parity)
if __name__=='__main__':main()

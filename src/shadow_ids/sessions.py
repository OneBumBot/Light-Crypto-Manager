"""Causal prefix aggregates. Final only after capture ended/drained; never backdated."""
import json,time

def aggregate(db,final=False):
 """Bounded journal rescan at run end/read-only analysis; no model calls or future early verdict."""
 from .models import frozen
 pins=frozen();values={}
 for row in db.db.execute('SELECT value FROM results ORDER BY rowid'):
  r=json.loads(row[0]);role=r['model_role']
  if role not in ['rf_session','if_session'] or r['score'] is None:continue
  key=(r['session_id'],role);v=values.setdefault(key,dict(n=0,total=0.0,maximum=float('-inf'),above=0,through_timestamp=0.0,first_timestamp=r['capture_timestamp']))
  v['n']+=1;v['total']+=r['score'];v['maximum']=max(v['maximum'],r['score']);v['above']+=int(r['comparison']);v['through_timestamp']=max(v['through_timestamp'],r['capture_timestamp'])
 out=[]
 for (session,role),v in values.items():
  selected=pins[role]['session'];method=selected['method'];score=v['total']/v['n'] if method=='mean' else v['maximum'] if method=='max' else v['above']/v['n']
  out.append(dict(session_id=session,model_role=role,method=method,score=score,threshold=selected['point']['threshold'],comparison=score>=selected['point']['threshold'],observations=v['n'],through_timestamp=v['through_timestamp'],evaluated_at=time.time(),final=final,finalization_reason='capture_end_observed_subset' if final else 'causal_prefix',scope='Observed supported packets, not Stage14 known-labelled-subset population',mode='SHADOW_ONLY',trusted_detector=False,device_binding='unbound'))
 return out

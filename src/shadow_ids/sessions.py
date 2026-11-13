"""Causal prefixes; final transport aggregate requires closure plus complete capture."""
import json,time

def aggregate(db,final=False):
 from .models import frozen
 pins=frozen();values={};closure={}
 for row in db.db.execute('SELECT packet FROM events ORDER BY ordinal'):
  try:e=json.loads(row[0])
  except (ValueError,TypeError):continue
  if type(e) is not dict or type(e.get('capture_id')) is not str:continue
  session=e.get('session')
  if type(session) is not str:continue
  key=e['capture_id']+':'+session;c=closure.setdefault(key,dict(syn=False,fins=set(),rst=False,complete=True,closed_observed_at=None));f=e.get('features',{});flags=f.get('tcp.flags') if type(f) is dict else None
  if type(flags) is not int or not 0<=flags<=511:c['complete']=False;flags=0
  c['complete'] &= e.get('status')=='FEATURE_READY' and not e.get('context_dropped',False)
  c['syn'] |= bool(flags&2 and not flags&16)
  if flags&1:c['fins'].add(e.get('direction'))
  if flags&4:c['rst']=True
  if c['rst'] or c['fins']=={0,1}:c['closed_observed_at']=e.get('feature_ready_at')
 for row in db.db.execute('SELECT value FROM results ORDER BY rowid'):
  r=json.loads(row[0]);role=r['model_role']
  if role not in ['rf_session','if_session'] or r['score'] is None:continue
  key=(r['session_id'],role);v=values.setdefault(key,dict(n=0,total=0.0,maximum=float('-inf'),above=0,through_timestamp=0.0,first_timestamp=r['capture_timestamp']))
  v['n']+=1;v['total']+=r['score'];v['maximum']=max(v['maximum'],r['score']);v['above']+=int(r['comparison']);v['through_timestamp']=max(v['through_timestamp'],r['capture_timestamp'])
 out=[]
 for (session,role),v in values.items():
  selected=pins[role]['session'];method=selected['method'];score=v['total']/v['n'] if method=='mean' else v['maximum'] if method=='max' else v['above']/v['n'];c=closure.get(session,{})
  closed=bool(final and c.get('syn') and c.get('complete') and (c.get('rst') or c.get('fins')=={0,1}));reason='observed_rst' if closed and c.get('rst') else 'bidirectional_fin' if closed else 'capture_boundary_partial_session' if final else 'causal_prefix'
  out.append(dict(session_id=session,model_role=role,method=method,score=score,threshold=selected['point']['threshold'],comparison=score>=selected['point']['threshold'],observations=v['n'],through_timestamp=v['through_timestamp'],evaluated_at=time.time(),final=closed,capture_view_final=bool(final),closed_observed_at=c.get('closed_observed_at'),finalization_reason=reason,scope='Observed supported transport packets; complete-capture plus SYN/FIN-or-RST required for final. Not Stage14 known-labelled subset.',mode='SHADOW_ONLY',trusted_detector=False,device_binding='unbound'))
 return out

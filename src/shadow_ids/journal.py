"""Separate bounded SQLite shadow authority; atomic idempotence, no telemetry/Policy tables."""
import json,os,sqlite3,time
from pathlib import Path
from contextlib import contextmanager
MAX_EVENTS=50000

def path_for(root):
 root=Path(root);new=root/'journal/shadow.db'
 return root/'shadow.db' if not new.exists() and (root/'shadow.db').exists() else new

def encode(value):return json.dumps(value,separators=(',',':'),allow_nan=False)
class Journal:
 def __init__(self,path,readonly=False):
  self.path=Path(path);self.retries=0;self.commits=0
  if self.path.is_symlink():raise ValueError('Journal symlink')
  if readonly:
   self.db=sqlite3.connect(self.path.resolve().as_uri()+'?mode=ro',uri=True,timeout=.2)
  else:
   os.umask(0o077);self.path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
   if self.path.parent.name=='journal':self.path.parent.chmod(0o750)
   self.db=sqlite3.connect(self.path,timeout=.2);self.path.chmod(0o640);self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA synchronous=FULL')
   self.db.executescript('CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY,run TEXT NOT NULL,ordinal INTEGER NOT NULL,created REAL NOT NULL,packet TEXT NOT NULL,processed INTEGER NOT NULL DEFAULT 0,UNIQUE(run,ordinal));CREATE INDEX IF NOT EXISTS pending ON events(processed,created);CREATE TABLE IF NOT EXISTS results(event_id TEXT NOT NULL,model_id TEXT NOT NULL,value TEXT NOT NULL,PRIMARY KEY(event_id,model_id));CREATE TABLE IF NOT EXISTS status(name TEXT PRIMARY KEY,value TEXT NOT NULL);CREATE TABLE IF NOT EXISTS session_stats(id TEXT PRIMARY KEY,value TEXT NOT NULL);')
  self.db.row_factory=sqlite3.Row
  if not readonly:
   for file in [self.path,Path(str(self.path)+'-wal'),Path(str(self.path)+'-shm')]:
    if file.exists():file.chmod(0o640)
 @contextmanager
 def write(self):
  if self.db.in_transaction:
   yield;return
  for attempt in range(6):
   try:self.db.execute('BEGIN IMMEDIATE');break
   except sqlite3.OperationalError as exc:
    if 'locked' not in str(exc).lower() and 'busy' not in str(exc).lower():raise
    if attempt==5:raise
    self.retries+=1;time.sleep(.005*2**attempt)
  try:yield
  except BaseException:self.db.rollback();raise
  else:self.db.commit();self.commits+=1
 def status(self,name,value):
  with self.write():self.db.execute('INSERT INTO status VALUES(?,?) ON CONFLICT(name) DO UPDATE SET value=excluded.value',(name,encode(value)))
 def append(self,event,capacity=512):
  if type(event) is not dict or event.get('mode')!='SHADOW_ONLY' or event.get('trusted_detector') is not False or event.get('device_binding')!='unbound':raise ValueError('Shadow trust/type invariant')
  if type(event.get('event_id')) is not str or type(event.get('ordinal')) is not int or len(encode(event))>8192:raise ValueError('Event bound')
  with self.write():
   if self.db.execute('SELECT 1 FROM events WHERE id=?',(event['event_id'],)).fetchone():return False
   if self.db.execute('SELECT COUNT(*) FROM events').fetchone()[0]>=MAX_EVENTS or self.db.execute('SELECT COUNT(*) FROM events WHERE processed=0').fetchone()[0]>=capacity:raise OverflowError('Explicit capture queue overflow')
   self.db.execute('INSERT INTO events VALUES(?,?,?,?,?,0)',(event['event_id'],event['capture_id'],event['ordinal'],time.time(),encode(event)))
  return True
 def pending(self,limit=64):return [dict(r) for r in self.db.execute('SELECT * FROM events WHERE processed=0 ORDER BY created,id LIMIT ?',(limit,))]
 def complete(self,row,results):
  with self.write():
   for result in results:
    if result.get('mode')!='SHADOW_ONLY' or result.get('trusted_detector') is not False or result.get('device_binding')!='unbound':raise ValueError('Result trust')
    inserted=self.db.execute('INSERT OR IGNORE INTO results VALUES(?,?,?)',(row['id'],result['model_id'],encode(result))).rowcount
    if inserted and result.get('score') is not None and result.get('model_role') in ['rf_session','if_session']:
     key=result['session_id']+':'+result['model_role'];old=self.db.execute('SELECT value FROM session_stats WHERE id=?',(key,)).fetchone();v=json.loads(old[0]) if old else dict(session_id=result['session_id'],model_role=result['model_role'],n=0,total=0.0,maximum=None,above=0)
     v.update(n=v['n']+1,total=v['total']+result['score'],maximum=max(v['maximum'] if v['maximum'] is not None else result['score'],result['score']),above=v['above']+int(result['comparison']),through_timestamp=result['capture_timestamp'],evaluated_at=result['inference_finish'])
     self.db.execute('INSERT INTO session_stats VALUES(?,?) ON CONFLICT(id) DO UPDATE SET value=excluded.value',(key,encode(v)))
   self.db.execute('UPDATE events SET processed=1 WHERE id=?',(row['id'],))
 def complete_batch(self,pairs):
  if not 1<=len(pairs)<=64:raise ValueError('Bounded result batch')
  with self.write():
   for row,results in pairs:self.complete(row,results)
 def snapshot(self,limit=25,offset=0,now=None):
  if type(limit) is not int or not 1<=limit<=100 or type(offset) is not int or not 0<=offset<=50000:raise ValueError('Pagination bound')
  now=time.time() if now is None else now
  states={r['name']:json.loads(r['value']) for r in self.db.execute('SELECT * FROM status')};capture=states.get('capture',{});worker=states.get('worker',{})
  for value in [capture,worker]:value['fresh']=isinstance(value.get('heartbeat'),(int,float)) and 0<=now-value['heartbeat']<=5
  last_packet=capture.get('last_packet');source_fresh=type(last_packet) in (int,float) and 0<=now-last_packet<=5
  worker['evidence_fresh']=type(worker.get('last_inference')) in (int,float) and 0<=now-worker['last_inference']<=5
  capture['traffic_state']='RECENT' if source_fresh else 'NO_RECENT_TRAFFIC'
  current=capture.get('fresh') and worker.get('fresh') and source_fresh and worker['evidence_fresh'] and worker.get('status')=='READY'
  if capture.get('status')=='CAPTURE_INCOMPLETE':current=False
  rows=[json.loads(r[0]) for r in self.db.execute('SELECT value FROM results ORDER BY rowid DESC LIMIT ? OFFSET ?',(limit,offset))] if current else []
  return dict(mode='SHADOW_ONLY',trusted_detector=False,device_binding='unbound',capture=capture,worker=worker,available=bool(current),results=rows,packets=self.db.execute('SELECT COUNT(*) FROM events').fetchone()[0],inferences=self.db.execute('SELECT COUNT(*) FROM results').fetchone()[0],pending=self.db.execute('SELECT COUNT(*) FROM events WHERE processed=0').fetchone()[0],source=states.get('source',{}),feature_parity=states.get('parity',{'status':'NOT_VERIFIED'}),sessions=self.db.execute("SELECT COUNT(DISTINCT json_extract(packet,'$.session')) FROM events").fetchone()[0],unknown=self.db.execute("SELECT COUNT(*) FROM events WHERE coalesce(json_extract(packet,'$.status'),'MALFORMED')!='FEATURE_READY'").fetchone()[0],session_aggregates=self.session_values(limit,offset) if current else [])
 def session_values(self,limit=25,offset=0):
  from .models import frozen
  pins=frozen();out=[]
  for row in self.db.execute('SELECT value FROM session_stats ORDER BY rowid DESC LIMIT ? OFFSET ?',(limit,offset)):
   v=json.loads(row[0]);p=pins[v['model_role']]['session'];method=p['method'];score=v['total']/v['n'] if method=='mean' else v['maximum'] if method=='max' else v['above']/v['n']
   out.append(dict(session_id=v['session_id'],model_role=v['model_role'],method=method,score=score,threshold=p['point']['threshold'],through_timestamp=v['through_timestamp'],evaluated_at=v['evaluated_at'],final=False,scope='causal_prefix_observed_supported_packets',mode='SHADOW_ONLY',trusted_detector=False,device_binding='unbound'))
  return out
 def close(self):self.db.close()

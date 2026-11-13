"""Additional diagnostic queue/freshness series; not pooled into controlled matrix."""
import json,threading,time
from pathlib import Path
from scripts.stage15_setup import lab
from scripts.stage15_runs import capture,workload,wait
from scripts.stage15_performance import start_worker
from src.shadow_ids.journal import Journal,path_for

def main():
 l=lab('.local-runtime/stage15/online');name='queue-observation-25';root=l.root/'shadow'/name;cid=capture(l,name,condition='rfif',duration=28);wid=start_worker(l,name,['rf_binary','if']);records=[];done=threading.Event()
 def observe():
  while not done.is_set():
   try:
    db=Journal(path_for(root),readonly=True);pending=db.db.execute('SELECT count(*) FROM events WHERE processed=0').fetchone()[0];oldest=db.db.execute("SELECT min(json_extract(packet,'$.capture_timestamp')) FROM events WHERE processed=0").fetchone()[0];last=db.db.execute('SELECT value FROM results ORDER BY rowid DESC LIMIT 1').fetchone();state=json.loads(last[0]) if last else None;db.close();now=time.time();records.append(dict(at=now,pending=pending,oldest_pending_age=now-oldest if oldest is not None else None,processed_source_age=now-state['capture_timestamp'] if state else None,last_inference_age=now-state['inference_finish'] if state else None))
   except Exception as exc:records.append(dict(at=time.time(),status=type(exc).__name__))
   done.wait(.5)
 thread=threading.Thread(target=observe);thread.start()
 try:truth=workload(l,name,25,.5,duration=20,seed=15970);wait(cid);wait(wid)
 finally:done.set();thread.join(3)
 counts=[r['pending'] for r in records if 'pending' in r];out=Path('docs/reports/stage15/queue-freshness.json');out.write_text(json.dumps(dict(records=records,sampled_max_pending=max(counts) if counts else None,capacity=512,sample_interval_seconds=.5,peak_between_samples='not_measured',actual_run_duration=truth['experiment_finished_at']-truth['experiment_started_at'],capture=json.loads((root/'capture-status.json').read_text()),source='Additional25-device diagnostic; not a replacement/extra independent repeat of48-run matrix',exit_code=0),indent=2));print('Actual sampled queue/freshness timeline saved; no zero-imputation; exit0')
if __name__=='__main__':main()

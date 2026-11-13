"""Actual same-tuple MQTT/TLS reconnect proof; old oracle discrepancy kept explicit."""
import csv,hashlib,json,os,subprocess,time
from pathlib import Path
from scripts.stage15_setup import lab
from scripts.stage15_runs import capture,wait
from scripts.stage15_performance import start_worker,state
from src.shadow_ids.journal import Journal,path_for
from src.research_stand.pcap_audit import packets

def main():
 l=lab('.local-runtime/stage15/online');name='tuple-reuse-real-v2';root=l.root/'shadow'/name;out=Path('docs/reports/stage15/tuple-reuse.json')
 if out.exists():raise ValueError('Immutable proof')
 # Install public probe code in the key-scoped publisher role, never the observer.
 l.run('cp',str(Path('scripts/stage15_tuple_probe.py').resolve()),'lab-devices:/tmp/stage15_tuple_probe.py')
 before=state(l);cid=capture(l,name,condition='all',duration=15);wid=start_worker(l,name,['rf_binary','if']);result=l.run('exec','-T','lab-devices','python','-c',"import runpy;runpy.run_path('/tmp/stage15_tuple_probe.py',run_name='__main__')",timeout=15);probe=json.loads(result.stdout);wait(cid);wait(wid);after=state(l);assert probe['tuple_reuse'] and all(r['mqtt_puback'] for r in probe['connections']);assert after['categories']['accepted']-before['categories']['accepted']==2
 l.run('run','--rm','--no-deps','--user',str(os.getuid())+':'+str(os.getgid()),'-v',str(root)+':/parity','traffic-collector','python','-m','src.research_stand.collector','extract','--directory','/parity')
 db=Journal(path_for(root),readonly=True);events=[json.loads(r[0]) for r in db.db.execute('SELECT packet FROM events ORDER BY ordinal')];db.close();reference=list(packets(root/'traffic.pcap'));export=list(csv.DictReader((root/'headers.csv').open()));syns=[];legacy_mismatches=0;last={};errors=0
 for event,p,row in zip(events,reference,export):
  if p['flags']&2 and not p['flags']&16:syns.append(dict(wire=p['wire'],sequence=p['sequence'],generation=event.get('session'),delta=event.get('features',{}).get('tcp.time_delta')))
  key=tuple(sorted((p['wire'][:2],p['wire'][2:])));legacy=p['time']-last.get(key,p['time']);last[key]=p['time'];f=event.get('features',{})
  if event['status']=='FEATURE_READY':
   legacy_mismatches+=int(abs(f['tcp.time_delta']-legacy)>1.1e-6)
   for key in ['frame.len','tcp.len','tcp.flags','tcp.window_size_value','tcp.time_delta']:
    value=int(row[key],0) if key=='tcp.flags' else float(row[key]);errors+=int(abs(f[key]-value)>(1.1e-6 if key=='tcp.time_delta' else 0))
 assert len(syns)>=2 and syns[0]['wire']==syns[1]['wire'] and syns[0]['generation']!=syns[1]['generation'] and syns[0]['delta']==syns[1]['delta']==0 and errors==0 and legacy_mismatches>=1
 out.write_text(json.dumps(dict(status='PASS',probe=probe,initial_syns=syns,tshark_mismatches=errors,legacy_tuple_delta_mismatches=legacy_mismatches,physical_packets=len(reference),old_oracle_unchanged=True,interpretation='Generation semantics match tshark; historical tuple-global delta check rejects this valid reuse boundary. No historical data/models rewritten.',pg_admissions=2,mongo_delta=after['mongo_records']-before['mongo_records'],exit_code=0),indent=2));print('Actual tuple reused, new generation delta0, independent tshark agrees; legacy-reference difference explicit; exit0')
if __name__=='__main__':main()

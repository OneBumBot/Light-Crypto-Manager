"""Tamper private copies of actual pilot PCAP/derived records, never scientific sources."""
import argparse,collections,csv,json,shutil
from pathlib import Path
from src.research_stand.label_verification import reconcile
from src.research_stand.dataset_v2 import build
from src.research_stand.pcap_audit import digest,headers
from scripts.stage14_collect import check_source


def read(path):
 with Path(path).open() as f:return list(csv.DictReader(f))


def derived_write(folder,rows):
 for name,records in [('observations.csv',rows),('dataset.csv',[r for r in rows if r['ground_truth']!='unknown'])]:
  with (folder/name).open('w') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(records)
 m=json.loads((folder/'dataset.manifest.json').read_text());known=[r for r in rows if r['ground_truth']!='unknown'];m.update(sha256=digest(folder/'dataset.csv'),observations_sha256=digest(folder/'observations.csv'),observations=len(rows),rows=len(known),unknown_excluded=len(rows)-len(known),captures=len({r['capture_id'] for r in known}),sessions=len({r['session_id'] for r in known}),class_counts=dict(collections.Counter(r['attack_type'] for r in known)));(folder/'dataset.manifest.json').write_text(json.dumps(m))


def main():
 p=argparse.ArgumentParser();p.add_argument('--captures',type=Path,default=Path('.local-runtime/stage14/pilot-captures'));p.add_argument('--dataset',type=Path,default=Path('.local-runtime/stage14/pilot-dataset'));p.add_argument('--output',type=Path,default=Path('docs/reports/stage14/real-negatives.json'));p.add_argument('--work',type=Path,default=Path('.local-runtime/stage14/negative-copies'));a=p.parse_args()
 if a.output.exists() or a.work.exists():p.error('Immutable probe report/copies')
 a.work.mkdir(mode=0o700,parents=True);original={str(p):digest(p) for p in a.captures.rglob('*') if p.is_file()};results=[]
 changes=['normal_to_violation','violation_to_normal','unknown_to_normal','unknown_to_violation','session','connection','time','reason','capture','source_hash','packet_scope','drop_unknown','qos1_promoted']
 for change in changes:
  folder=a.work/change;shutil.copytree(a.dataset,folder);rows=read(folder/'observations.csv')
  if '_to_' in change:
   old,new=change.split('_to_');old='controlled_violation' if old=='violation' else old;new='controlled_violation' if new=='violation' else new;row=next(r for r in rows if r['ground_truth']==old);row.update(ground_truth=new,label='1' if new=='controlled_violation' else '0',attack_type='ControlledViolation' if new=='controlled_violation' else 'Normal')
  elif change=='qos1_promoted':
   row=next(r for r in rows if r['scenario_category']=='qos1_retry' and r['ground_truth']=='normal');row.update(ground_truth='controlled_violation',label='1',attack_type='ControlledViolation')
  elif change=='drop_unknown':rows.remove(next(r for r in rows if r['ground_truth']=='unknown'))
  else:
   field={'session':'session_id','connection':'connection_id','time':'epoch_seconds','reason':'label_reason','capture':'capture_id','source_hash':'source_pcap_sha256','packet_scope':'label_unit'}[change];rows[1][field]=str(float(rows[1][field])+.1) if change=='time' else 'forged-value'
  derived_write(folder,rows)
  try:reconcile(folder,a.captures)
  except ValueError as e:results.append(dict(case=change,coherent_derived_hashes=True,rejected=True,diagnostic=str(e)))
  else:raise AssertionError('Coherent tampering accepted:'+change)
 # Actual sources, with faults confined to private copies. No new independent capture is claimed.
 choices={json.loads((p/'ground-truth.json').read_text())['experiment']['scenario']:p for p in a.captures.iterdir() if p.is_dir()}
 for case in ['missing_pcap','truncated_pcap','pcap_hash','missing_broker','missing_observer','clock_drift','nonfinite_clock','missing_tls_close','ambiguous_broker_session']:
  source=choices['regular'];folder=a.work/case/source.name;shutil.copytree(source,folder)
  if case=='missing_pcap':(folder/'traffic.pcap').unlink()
  elif case=='truncated_pcap':
   f=folder/'traffic.pcap';f.write_bytes(f.read_bytes()[:-7])
   for name in ['capture.json','extractor.json']:
    f=folder/name;m=json.loads(f.read_text());m['pcap_sha256']=digest(folder/'traffic.pcap');f.write_text(json.dumps(m))
  elif case=='pcap_hash':
   for name in ['capture.json','extractor.json']:
    f=folder/name;m=json.loads(f.read_text());m['pcap_sha256']='0'*64;f.write_text(json.dumps(m))
  elif case in ['missing_broker','missing_observer']:(folder/('broker-evidence.json' if case=='missing_broker' else 'mqtt-observer.json')).unlink()
  elif case in ['clock_drift','nonfinite_clock','missing_tls_close']:
   f=folder/'ground-truth.json';m=json.loads(f.read_text())
   if case=='missing_tls_close':m['connections'][0]['closed_at']=None
   else:m['clock']['wall_monotonic_drift_seconds']=4 if case=='clock_drift' else float('nan')
   f.write_text(json.dumps(m))
  else:
   f=folder/'broker-evidence.json';m=json.loads(f.read_text());m['sessions']+=m['sessions'];f.write_text(json.dumps(m));out=a.work/(case+'-dataset');build(folder.parent,out);r=read(out/'observations.csv');assert all(v['ground_truth']=='unknown' for v in r);results.append(dict(case=case,rejected=True,mechanism='ambiguous sessions remain unknown'));continue
  try:check_source(folder)
  except (ValueError,KeyError,TypeError,OSError) as e:results.append(dict(case=case,rejected=True,diagnostic=type(e).__name__+':'+str(e)))
  else:raise AssertionError('Bad source accepted:'+case)
 for case in ['wrong_digest','wrong_epoch','wrong_sequence','missing_prior','late_prior','acl_outside_window','fake_intent']:
  source=choices['replay'] if case not in ['acl_outside_window','fake_intent'] else choices['forbidden_acl'] if case=='acl_outside_window' else choices['regular'];folder=a.work/case/source.name;shutil.copytree(source,folder);truth=json.loads((folder/'ground-truth.json').read_text())
  if case=='wrong_digest':
   f=folder/'mqtt-observer.json';m=json.loads(f.read_text())
   for event in m['events']:
    if event.get('payload_sha256'):event['payload_sha256']='f'*64
  elif case in ['wrong_epoch','wrong_sequence','missing_prior','late_prior']:
   f=folder/'core.json';m=json.loads(f.read_text());actor=next(r for r in truth['connections'] if r['activity']=='replay')
   for e in m['security_events']:
    if e['device_id']==actor['logical_device'] and e['category']=='accepted':
     if case=='wrong_epoch':e['key_epoch']+=100
     elif case=='wrong_sequence':e['sequence_number']+=100000
     elif case=='missing_prior':e['category']='not_accepted'
     else:e['occurred_at']=actor['closed_at']+100
  elif case=='acl_outside_window':
   f=folder/'broker-evidence.json';m=json.loads(f.read_text())
   for session in m['sessions']:
    for e in session['events']:
     if e['kind']=='acl_denied':e['at']=session['closed_at']+100
  else:
   f=folder/'ground-truth.json';m=truth
   for r in m['connections']:r['activity']='bad_credentials';r['auth_rejected']=True
  f.write_text(json.dumps(m));out=a.work/(case+'-dataset');build(folder.parent,out);rows=read(out/'observations.csv');assert not any(r['ground_truth']=='controlled_violation' for r in rows);results.append(dict(case=case,rejected=True,mechanism='contradictory activity remains unverified/unknown'))
 source=choices['regular'];root=a.work/'duplicate-copy';shutil.copytree(source,root/source.name);other=root/'renamed-for-probe';shutil.copytree(source,other);p=other/'ground-truth.json';r=json.loads(p.read_text());r['experiment']['experiment_id']=other.name;p.write_text(json.dumps(r))
 try:build(root,a.work/'duplicate-dataset')
 except ValueError as e:assert 'Duplicate source PCAP' in str(e);results.append(dict(case='duplicate_physical_pcap_new_id',rejected=True,diagnostic=str(e)))
 else:raise AssertionError('Duplicate PCAP accepted')
 assert original=={str(p):digest(p) for p in a.captures.rglob('*') if p.is_file()}
 a.output.write_text(json.dumps(dict(real_pilot_sources=True,deliberate_private_copies_not_independent_experiments=True,original_sources_unchanged=True,cases=results,exit_code=0),indent=2));print('Actual-source tamper checks',len(results),'exit0')
if __name__=='__main__':main()

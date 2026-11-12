"""Read-only full-journal source census for fault cohorts; no lossless assumption."""
import argparse,hashlib,json
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
from scripts.performance_lab import Lab


def main():
    p=argparse.ArgumentParser();p.add_argument('--directories',nargs='+',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--fault-report',type=Path);a=p.parse_args()
    if a.output.exists():p.error('Immutable report exists')
    reports=[]
    faults=json.loads(a.fault_report.read_text()) if a.fault_report else None
    for directory in a.directories:
        lab=Lab(directory);lab.run('up','-d','--no-deps','--wait','postgres','mongo')
        try:
            data=lab.probe('export',start='1970-01-01T00:00:00+00:00',end=datetime.now(timezone.utc).isoformat())
            admitted={(r['device_id'],r['key_epoch'],r['sequence_number']) for r in data['rows']};devices=[];fault_counts=[]
            if faults and faults['project']==lab.project:
                fault_counts=[dict(service=f['service'],start=f['start'],restored=f['restored'],formed=0,matched_pg=0,unconfirmed=0) for f in faults['faults']]
            for device in lab.devices:
                raw=lab.run('run','--rm','--no-deps','--entrypoint','cat','device-'+device,'/device/research-events.jsonl').stdout
                rows=[json.loads(line) for line in raw.splitlines()]
                if len(rows)>=50000:raise ValueError('Journal cap reached; census may be incomplete')
                formed=[r for r in rows if r['kind']=='formed'];calls=[r for r in rows if r['kind']=='publish'];acks={(r['boot'],r['mid']) for r in rows if r['kind']=='puback' and r['success']}
                identities={(device,r['epoch'],r['sequence']) for r in formed};missing=identities-admitted
                reconnects=Counter(r['boot'] for r in rows if r['kind']=='connect' and r['success'])
                for f in fault_counts:
                    selected=[r for r in formed if datetime.fromisoformat(f['start']).timestamp()<=r['wall_ns']/1e9<=datetime.fromisoformat(f['restored']).timestamp()]
                    f['formed']+=len(selected);f['matched_pg']+=sum((device,r['epoch'],r['sequence']) in admitted for r in selected);f['unconfirmed']=f['formed']-f['matched_pg']
                devices.append(dict(mqtt_reconnects_same_process=sum(max(0,n-1) for n in reconnects.values()),device=device,journal_events=len(rows),journal_sha256=hashlib.sha256(raw.encode()).hexdigest(),formed=len(formed),publish_called=len(calls),queued=sum(r['queued'] for r in calls),puback_joined=sum((r['boot'],r['mid']) in acks for r in calls),matched_pg=len(identities&admitted),formed_unconfirmed=len(missing),missing_identities=sorted(missing)[:1000],source_identity_duplicates=len(formed)-len(identities),disconnect_observations=sum(r['kind']=='disconnect' for r in rows)))
            reports.append(dict(project=lab.project,fault_source_intervals=fault_counts,devices=devices,source_formed=sum(d['formed'] for d in devices),source_matched=sum(d['matched_pg'] for d in devices),source_unconfirmed=sum(d['formed_unconfirmed'] for d in devices),pg_admitted=len(admitted),pg_identity_sha256=hashlib.sha256(json.dumps(sorted(admitted)).encode()).hexdigest(),scope='entire preserved agent journal, including faults/shutdown; external poison publishers excluded from source census',commands=lab.commands))
        finally:lab.run('stop')
    a.output.write_text(json.dumps(dict(projects=reports,exit_code=0,limitations=['Journal line-buffered, not crash-durable; unsaved formed event cannot be counted','Unconfirmed source identity is not automatically classified as permanent loss','Disconnect observations include deliberate SIGTERM/recreation as well as failures']),indent=2));print([(r['project'],r['source_formed'],r['source_unconfirmed']) for r in reports])

if __name__=='__main__':main()

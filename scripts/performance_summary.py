"""Derive per-device and per-run statistics without rewriting raw experiment reports."""
import argparse,json,gzip
from pathlib import Path
from datetime import datetime
from scripts.performance_run import describe


def read_json(path):
    if path.exists():return json.loads(path.read_text())
    with gzip.open(str(path)+'.gz','rt') as f:return json.load(f)


def main():
    p=argparse.ArgumentParser();p.add_argument('--reports',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():p.error('Immutable summary exists')
    runs=[]
    for path in sorted(a.reports.glob('*/result.json')):
        r=json.loads(path.read_text());raw=read_json(path.parent/'committed.json')['rows'];events=read_json(path.parent/'agent-events.json')
        devices={}
        for device in sorted({e['device'] for e in events if e['kind']=='formed'}):
            formed=[e for e in events if e['kind']=='formed' and e['device']==device];rows=[e for e in raw if e['device_id']==device]
            devices[device]=dict(formed=len(formed),pg_window=len(rows),build_ns=describe([e['build_ns'] for e in formed]),payload_bytes=describe([e['bytes'] for e in formed]),profiles=sorted({e['profile'] for e in formed}),measured_to_received_seconds=describe([(datetime.fromisoformat(e['created_at'])-datetime.fromisoformat(e['payload']['measured_at'])).total_seconds() for e in rows]))
        runs.append(dict(experiment_id=path.parent.name,project=r['project'],duration=r['duration'],provisioned_devices=r['devices'],active_publishers_observed=len(devices),per_device=devices,
                         scheduled=r['planned'],formed=r['formed'],queued=r['queued'],puback_joined=r['puback_joined'],pg_window=r['committed_in_time_window'],source_joined=r['formed_matching_pg'],source_unmatched_window=r['formed_not_in_pg_window'],
                         pg_total_after=r['after']['counters'].get('accepted',0),mongo_total_after=r['after']['mongo_managed'],backlog_after={k:v for k,v in r['after']['outbox'].items() if k!='delivered'},
                         rate=r['throughput'],cpu=r['cpu_percent'],ram=r['ram_mib'],delivery_latency=r['measured_to_delivery_finish_seconds'],nonce_duplicates=r['nonce_duplicates'],reconnects=r['reconnects']))
    micro=json.loads((a.reports/'crypto-microbenchmark.json').read_text());repeat_stats=[]
    for profile in ['ascon-aead128-v1','aes-128-gcm-v1']:
        for size in sorted({r['size'] for r in micro['runs']}):
            selected=[r for r in micro['runs'] if r['profile']==profile and r['size']==size]
            repeat_stats.append(dict(profile=profile,size=size,independent_runs=len(selected),mean_encrypt_ns=describe([r['summary']['encrypt_ns']['mean'] for r in selected]),mean_decrypt_ns=describe([r['summary']['decrypt_ns']['mean'] for r in selected]),confidence_interval='not_estimated: only three independent runs; no packet pseudo-replication'))
    a.output.write_text(json.dumps(dict(runs=runs,micro_per_run=repeat_stats,limitations=['One cohort run per load, no capacity extrapolation','Window boundary mismatches are not proven losses','Post-drain Mongo and PG totals, not publish() counts','Resource samples are correlated; no independent-run confidence interval']),indent=2))
    print('Per-device/run summary written')

if __name__=='__main__':main()

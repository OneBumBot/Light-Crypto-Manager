"""Derive run-level statistics from real source identities; keep censored events explicit."""
import argparse,json,statistics,csv,hashlib
from pathlib import Path
from datetime import datetime
from scripts.performance_run import describe


def dt(value):return datetime.fromisoformat(value)


def one(folder):
    r=json.loads((folder/'result.json').read_text());samples=json.loads((folder/'samples.json').read_text());ledger=json.loads((folder/'ledger-final.json').read_text());agents=json.loads((folder/'agents.json').read_text())
    start,end=dt(r['start_wall']),dt(r['end_wall']);s0,s1=r['before'],r['inflight'];interval=(dt(s1['at'])-dt(s0['at'])).total_seconds()
    source_in=s1['security']['total']-s0['security']['total'];processed=s1['security']['consumed']-s0['security']['consumed']
    assert s1['security']['pending']==s0['security']['pending']+source_in-processed
    assert ledger['duplicate_markers']==ledger['duplicate_decisions']==ledger['policy_applied']==ledger['transitions']==0
    formed=[v for v in agents if v['kind']=='formed' and start.timestamp()*1e9<=v['wall_ns']<end.timestamp()*1e9]
    window=[v for v in agents if start.timestamp()*1e9<=v['wall_ns']<end.timestamp()*1e9]
    pub=[v for v in window if v['kind']=='publish'];ack={(v['device'],v['boot'],v['mid']) for v in agents if v['kind']=='puback' and v['success']}
    ids={(v['device'],v['epoch'],v['sequence']) for v in formed};pg={(v['device_id'],v['key_epoch'],v['sequence_number']) for v in ledger['outbox_rows']};mongo={(v['device_id'],v['key_epoch'],v['sequence_number']) for v in ledger['mongo_rows']}
    missing_pg=ids-pg;missing_mongo=ids-mongo
    if r['variant']=='optimized':assert not missing_pg and not missing_mongo and all(v['processed_at'] for v in ledger['source_rows'])
    assert ledger['source_count']==len(ledger['source_rows']) and len(pg)==len(ledger['outbox_rows'])
    sources=[v for v in ledger['source_rows'] if start<=dt(v['occurred_at'])<end];timings=[];after_stop=[];censored=0
    for v in sources:
        if v['processed_at'] is None:censored+=1;continue
        lag=(dt(v['processed_at'])-dt(v['occurred_at'])).total_seconds()
        (timings if dt(v['processed_at'])<=end else after_stop).append(lag)
    worker_cpu=[];worker_ram=[];heartbeat=[];freshness=[];rows=[]
    for i,v in enumerate(samples):
        snap=v['snapshot'];at=dt(snap['at']);last=snap['last_processed']['evidence_at'];evidence_age=(at-dt(last)).total_seconds() if last else None
        ws=snap['worker'];hb=(at-dt(ws[0]['heartbeat_at'])).total_seconds() if ws else None
        heartbeat.append(hb);freshness.append(evidence_age)
        for c in v['resources']['containers']:
            if c['Name'].endswith('-policy-worker-1'):
                worker_cpu.append(float(c['CPUPerc'].strip('%')))
                raw=c['MemUsage'].split('/')[0].strip();import re
                m=re.fullmatch(r'([\d.]+)([KMG]?i?B)',raw);worker_ram.append(float(m[1])*{'KiB':1/1024,'MiB':1,'GiB':1024,'B':1/2**20}[m[2]])
        previous=samples[i-1]['snapshot'] if i else None
        elapsed=(at-dt(previous['at'])).total_seconds() if previous else None
        rows.append(dict(elapsed=v['elapsed'],pending=snap['security']['pending'],oldest_age=snap['security']['oldest_pending_age'],evidence_age=evidence_age,heartbeat_age=hb,incoming_per_second=(snap['security']['total']-previous['security']['total'])/elapsed if previous else None,processed_per_second=(snap['security']['consumed']-previous['security']['consumed'])/elapsed if previous else None,lock_waits=snap['lock_waits'],pg_connections=snap['db']['numbackends']))
    good_cost=[v['cost'] for v in samples if v['cost']]
    a,b=good_cost[0],good_cost[-1];n=b['processed']-a['processed']
    sql_calls=(b['sql_count']-a['sql_count'])/n if n else None;transactions=(b['commits']-a['commits'])/n if n else None
    admission=None;p=folder/'admission-timings.jsonl'
    if p.exists():
        raw=[json.loads(line) for line in p.read_text().splitlines()];valid=[v for v in raw if v['outcome']=='admitted' and start.timestamp()*1e9<=v['finished_wall_ns']<end.timestamp()*1e9]
        admission=dict(recorded_successes=len(valid),transaction_wall_seconds=describe([t['nanoseconds']/1e9 for v in valid for t in v['transactions'] if t['committed']]),total_process_packet_seconds=describe([v['total_ns']/1e9 for v in valid]),boundary='engine.begin enter through successful exit; includes checkout/pre-ping/SQL/commit, not isolated server execution; matched lab instrumentation')
    per_device={}
    for device in sorted({v['device_id'] for v in sources if v['device_id'] is not None}):
        vals=[v for v in sources if v['device_id']==device]
        per_device[device]=dict(source_events=len(vals),unprocessed=sum(v['processed_at'] is None for v in vals),recorded_latency_seconds=describe([(dt(v['processed_at'])-dt(v['occurred_at'])).total_seconds() for v in vals if v['processed_at']]))
    xs=[v['elapsed'] for v in rows];ys=[v['pending'] for v in rows];xm=statistics.mean(xs);ym=statistics.mean(ys)
    slope=sum((x-xm)*(y-ym) for x,y in zip(xs,ys))/sum((x-xm)**2 for x in xs) if len(xs)>1 else None
    result=dict(project=r['project'],variant=r['variant'],devices=r['devices'],requested_seconds=r['requested_seconds'],kind=r.get('experiment_kind','policy_throughput'),source_sha=r['source_sha'],controller_source_hashes=r['source_hashes'],rules_sha=s1['sha256'],active_version=s1['version'],source_interval_seconds=interval,incoming_observations=source_in,processed_observations=processed,incoming_per_second=source_in/interval,processed_per_second=processed/interval,initial_pending=s0['security']['pending'],inflight_pending=s1['security']['pending'],retained=ledger['source_count'],capacity=s1['capacity'],overflow=s1['capacity']['overflow'],final_pending=sum(v['processed_at'] is None for v in ledger['source_rows']),drain_seconds=r['drain_seconds'],source_window_rows=len(sources),latency_inflight_seconds=describe(timings),latency_drain_seconds=describe(after_stop),unprocessed_censored=censored,latency_note='Conditional on recorded processing phase; pending is censored, never a zero latency',scheduled=sum(v['count'] for v in window if v['kind']=='scheduled'),formed=len(formed),publish_calls=len(pub),queued=sum(v['queued'] for v in pub),puback_joined=sum((v['device'],v['boot'],v['mid']) in ack for v in pub),formed_pg_matches=len(ids&pg),formed_mongo_matches=len(ids&mongo),formed_unconfirmed_pg=len(missing_pg),formed_unconfirmed_mongo=len(missing_mongo),pg_committed=len(pg),mongo_stored=len(mongo),source_duplicate_ids=len(formed)-len(ids),nonce_duplicates=r['nonce_duplicates'],source_statuses=ledger['source_counts_by_status'],policy_worker_cpu_percent=describe(worker_cpu),policy_worker_ram_mib=describe(worker_ram),total_cpu_percent=describe([v['resources']['cpu_percent'] for v in samples]),total_ram_mib=describe([v['resources']['ram_mib'] for v in samples]),instrumented_client_sql_calls_per_process_attempt=sql_calls,instrumented_application_commits_per_process_attempt=transactions,sql_instrumentation_limit='SQLAlchemy cursor/commit hooks exclude driver-internal pre-ping, trigger/internal PostgreSQL statements; not all DB transactions',admission=admission,timeseries=rows,per_device=per_device,descriptive_pending_slope_per_second=slope,max_recorded_oldest_pending_age=max((v['oldest_age'] for v in rows if v['oldest_age'] is not None),default=None),exit_code=0)
    assert result['overflow']==0
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--reports',type=Path,default=Path('docs/reports/stage13'));a=p.parse_args();runs=[one(f.parent) for f in sorted(a.reports.glob('*r*/result.json'))]
    summary=dict(runs=runs,scope='independent projects/runs; packet percentiles descriptive and censored counts explicit; no CI from correlated packets',policy='DRY_RUN',trusted_detector=False,exit_code=0)
    (a.reports/'performance-summary.json').write_text(json.dumps(summary,indent=2))
    keys=['project','variant','kind','devices','requested_seconds','incoming_per_second','processed_per_second','initial_pending','inflight_pending','final_pending','drain_seconds','pg_committed','mongo_stored','overflow','formed','formed_unconfirmed_pg','formed_unconfirmed_mongo']
    with (a.reports/'run-summary.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys,lineterminator='\n');w.writeheader();w.writerows({k:r[k] for k in keys} for r in runs)
    print('Derived',len(runs),'measured run summaries; exit0')
if __name__=='__main__':main()

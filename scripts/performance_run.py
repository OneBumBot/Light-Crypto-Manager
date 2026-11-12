"""Bounded real MQTT cohort observation. Lab must already be running."""
import argparse,csv,json,os,platform,re,shutil,statistics,subprocess,time
from pathlib import Path
from datetime import datetime,timezone
import requests
from scripts.performance_lab import Lab


def describe(values):
    if not values:return dict(n=0)
    v=sorted(values);n=len(v)
    r=dict(n=n,mean=statistics.mean(v),median=statistics.median(v),stddev=statistics.stdev(v) if n>1 else None,min=v[0],max=v[-1])
    for key,p,minimum in [('p95',.95,200),('p99',.99,1000)]:r[key]=v[int((n-1)*p)] if n>=minimum else 'insufficient_samples'
    return r


def login(lab,role='admin'):
    session=requests.Session();url=lab.url();r=session.get(url+'/login',timeout=8);r.raise_for_status()
    token=re.search(r'name="csrf_token"[^>]*value="([^"]+)"',r.text).group(1)
    r=session.post(url+'/login',data=dict(username='demo-'+role,password=(lab.root/'accounts'/(role+'.password')).read_text().strip(),csrf_token=token),timeout=8);r.raise_for_status()
    if r.url.endswith('/login'):raise AssertionError('Lab login failed')
    token=re.search(r'name="csrf-token" content="([^"]+)"',r.text).group(1)
    return session,url,token


def resources(lab):
    ids=lab.run('ps','-q').stdout.split()
    r=subprocess.run(['docker','stats','--no-stream','--format','{{json .}}',*ids],capture_output=True,text=True,timeout=20,check=True)
    rows=[json.loads(x) for x in r.stdout.splitlines()]
    def mib(s):
        m=re.fullmatch(r'([\d.]+)([KMGTP]?i?B)',s.strip());return float(m[1])*{'B':1/2**20,'kB':1/1024,'KiB':1/1024,'MiB':1,'GiB':1024,'TiB':1024**2}.get(m[2],1)
    return dict(cpu_percent=sum(float(x['CPUPerc'].strip('%')) for x in rows),ram_mib=sum(mib(x['MemUsage'].split('/')[0]) for x in rows),containers=rows)


def observe(lab,seconds,output):
    if output.exists():raise ValueError('Immutable report exists')
    output.mkdir(parents=True);session,url,_=login(lab);before=lab.probe('snapshot');start_wall=time.time();start=time.monotonic();samples=[];reason='duration_complete'
    try:
        while time.monotonic()-start<seconds:
            row=dict(elapsed=time.monotonic()-start,wall=datetime.now(timezone.utc).isoformat(),**resources(lab))
            row['sql']=lab.probe('snapshot');row['http']=[]
            for route in ['/api/monitoring','/api/monitoring/alpha','/api/telemetry/history?device_id=alpha&limit=50']:
                t=time.perf_counter();r=session.get(url+route,timeout=8);row['http'].append(dict(route=route,status=r.status_code,seconds=time.perf_counter()-t,bytes=len(r.content)))
            samples.append(row);(output/'samples.json').write_text(json.dumps(samples,indent=2))
            available=int(next(l.split()[1] for l in Path('/proc/meminfo').read_text().splitlines() if l.startswith('MemAvailable:')))*1024
            backlog=sum(v for k,v in row['sql']['outbox'].items() if k!='delivered')
            accepted=row['sql']['counters'].get('accepted',0)-before['counters'].get('accepted',0)
            if available<8*2**30 or shutil.disk_usage(output).free<4*2**30 or row['ram_mib']>8192 or row['cpu_percent']>800 or backlog>5000 or accepted>100000 or sum(p.stat().st_size for p in output.rglob('*') if p.is_file())>256*2**20:
                reason='resource_stop';break
            time.sleep(max(0,min(10,seconds-(time.monotonic()-start))))
    finally:
        end_wall=time.time();lab.run('stop',*lab.agents());drain=time.monotonic()+90
        while time.monotonic()<drain:
            after=lab.probe('snapshot')
            if not sum(v for k,v in after['outbox'].items() if k!='delivered'):break
            time.sleep(2)
    exported=lab.probe('export',start=datetime.fromtimestamp(start_wall,timezone.utc).isoformat(),end=datetime.fromtimestamp(end_wall,timezone.utc).isoformat())
    (output/'committed.json').write_text(json.dumps(exported,indent=2))
    journal=[]
    for device in lab.devices:
        r=lab.run('run','--rm','--no-deps','--entrypoint','cat','device-'+device,'/device/research-events.jsonl',timeout=30)
        events=[dict(json.loads(x),device=device) for x in r.stdout.splitlines()]
        journal.extend(e for e in events if start_wall*1e9<=e['wall_ns']<=end_wall*1e9)
    (output/'agent-events.json').write_text(json.dumps(journal,indent=2))
    formed=[e for e in journal if e['kind']=='formed'];pubs=[e for e in journal if e['kind']=='publish'];acks={(e['device'],e['boot'],e['mid']) for e in journal if e['kind']=='puback' and e['success']}
    identity=lambda r:(r['device_id'],r['key_epoch'],r['sequence_number'])
    pg={identity(r) for r in exported['rows']};fg={(e['device'],e['epoch'],e['sequence']) for e in formed}
    nonces=[(e['device'],e['profile'],e['nonce']) for e in formed]
    rows=exported['rows'];receive=[];deliver=[];full=[]
    for r in rows:
        measured=datetime.fromisoformat(r['payload']['measured_at']).timestamp();received=datetime.fromisoformat(r['created_at']).timestamp()
        receive.append(received-measured)
        if r['delivered_at']:
            delivered=datetime.fromisoformat(r['delivered_at']).timestamp();deliver.append(delivered-received);full.append(delivered-measured)
    result=dict(project=lab.project,git_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),source_dirty=subprocess.check_output(['git','status','--porcelain'],text=True).strip()!='',
      devices=len(lab.devices),requested_duration=seconds,duration=end_wall-start_wall,interval=.5,stop_reason=reason,
      planned=sum(e['count'] for e in journal if e['kind']=='scheduled'),formed=len(formed),publish_called=len(pubs),queued=sum(e['queued'] for e in pubs),puback_joined=sum((e['device'],e['boot'],e['mid']) in acks for e in pubs),
      committed_in_time_window=len(rows),formed_matching_pg=len(fg&pg),formed_not_in_pg_window=len(fg-pg),nonce_duplicates=len(nonces)-len(set(nonces)),
      counters_delta={k:after['counters'].get(k,0)-before['counters'].get(k,0) for k in set(before['counters'])|set(after['counters'])},before=before,after=after,
      throughput=len(rows)/(end_wall-start_wall),cpu_percent=describe([s['cpu_percent'] for s in samples]),ram_mib=describe([s['ram_mib'] for s in samples]),
      measured_to_received_seconds=describe(receive),received_to_delivery_finish_seconds=describe(deliver),measured_to_delivery_finish_seconds=describe(full),
      http={route:describe([h['seconds'] for s in samples for h in s['http'] if h['route']==route]) for route in [h['route'] for h in samples[0]['http']]},
      reconnects=sum(e['kind']=='disconnect' for e in journal),db_reconnects='not_measured',pg_commit_latency='not_measured',mongo_commit_timestamp='not_measured',
      environment=dict(platform=platform.platform(),python=platform.python_version(),cpu_count=os.cpu_count(),cpu_model=next(l.split(':',1)[1].strip() for l in Path('/proc/cpuinfo').read_text().splitlines() if l.startswith('model name'))),commands=lab.commands,exit_code=0)
    result['image_versions']=json.loads(lab.run('images','--format','json').stdout)
    result['source_files']={p:__import__('hashlib').sha256(Path(p).read_bytes()).hexdigest() for p in subprocess.check_output(['git','ls-files','src','scripts','Dockerfile'],text=True).splitlines() if Path(p).is_file()}
    (output/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps({k:result[k] for k in ['devices','duration','throughput','formed','formed_matching_pg','nonce_duplicates','stop_reason']},indent=2))
    with (output/'timings.csv').open('w') as f:
        writer=csv.writer(f);writer.writerow(['device_id','sequence','measured_at','received_at','delivery_finish_at'])
        for r in rows:writer.writerow([r['device_id'],r['sequence_number'],r['payload']['measured_at'],r['created_at'],r['delivered_at']])


def main():
    p=argparse.ArgumentParser();p.add_argument('--directory',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--seconds',type=int,default=300);a=p.parse_args()
    if not 30<=a.seconds<=1800:p.error('Bounded 30..1800 seconds')
    observe(Lab(a.directory),a.seconds,a.output)

if __name__=='__main__':main()

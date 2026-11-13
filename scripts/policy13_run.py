"""One bounded comparable real MQTT run, retaining all source identities and costs."""
import argparse,json,time,subprocess,hashlib,platform,shutil
from pathlib import Path
from datetime import datetime,timezone
from scripts.policy_lab import Lab
from scripts.performance_run import resources


def probe(lab,action='snapshot'):
    path=Path('scripts/policy13_probe.py').resolve()
    r=lab.run('run','--rm','-T','--no-deps','-v',str(path)+':/app/scripts/policy13_probe.py:ro','--entrypoint','python','tests','-m','scripts.policy13_probe',action)
    return json.loads(r.stdout)


def observe(lab,seconds,output,variant,receiver_profile=False):
    if output.exists():raise ValueError('New report directory required')
    output.mkdir(parents=True)
    profile=Path('scripts/policy13_worker_profile.py').resolve()
    override=lab.root/'profile.compose.json';override.write_text(json.dumps({'services':{'policy-worker':{'command':['python','-m','scripts.policy13_worker_profile'],'volumes':[str(profile)+':/app/scripts/policy13_worker_profile.py:ro']}}}));override.chmod(0o600)
    if receiver_profile:
        config=json.loads(override.read_text());receiver=Path('scripts/policy13_receiver_profile.py').resolve();config['services']['receiver']={'command':['python','-m','scripts.policy13_receiver_profile'],'volumes':[str(receiver)+':/app/scripts/policy13_receiver_profile.py:ro']};override.write_text(json.dumps(config))
    lab.base+=['-f',str(override)]
    if receiver_profile:lab.run('up','-d','--no-deps','--wait','receiver')
    lab.run('up','-d','--no-deps','--wait','policy-worker')
    start=time.monotonic();samples=[];reason='duration_complete'
    source=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    images=json.loads(lab.run('images','--format','json').stdout)
    before=probe(lab);start_wall=datetime.now(timezone.utc).isoformat()
    (output/'schema.json').write_text(json.dumps(probe(lab,'schema'),indent=2))
    start=time.monotonic();start_wall=datetime.now(timezone.utc).isoformat()
    try:
        while time.monotonic()-start<seconds:
            snap=probe(lab)
            cost=lab.run('exec','-T','policy-worker','cat','/tmp/policy-cost.json',check=False)
            row=dict(elapsed=time.monotonic()-start,snapshot=snap,cost=json.loads(cost.stdout) if cost.returncode==0 else None,resources=resources(lab))
            samples.append(row);(output/'samples.json').write_text(json.dumps(samples,indent=2))
            if snap['capacity']['overflow'] or snap['security']['pending']>60000 or sum(v for k,v in snap['outbox'].items() if k!='delivered')>5000 or row['resources']['ram_mib']>8192 or row['resources']['cpu_percent']>800 or shutil.disk_usage(output).free<4*2**30:
                reason='resource_stop';break
            time.sleep(min(5,max(0,seconds-(time.monotonic()-start))))
    finally:
        actual_seconds=time.monotonic()-start;end_wall=datetime.now(timezone.utc).isoformat();inflight=probe(lab);lab.run('stop',*lab.agents());drain_start=time.monotonic();drain=[]
        deadline=drain_start+300
        while time.monotonic()<deadline:
            snap=probe(lab);drain.append(dict(elapsed=time.monotonic()-drain_start,snapshot=snap))
            (output/'drain.json').write_text(json.dumps(drain,indent=2))
            if not snap['security']['pending'] and not sum(v for k,v in snap['outbox'].items() if k!='delivered'):break
            time.sleep(3)
        after=probe(lab)
        if receiver_profile:
            r=lab.run('exec','-T','receiver','cat','/tmp/policy13-admission.jsonl');(output/'admission-timings.jsonl').write_text(r.stdout)
        cost=lab.run('exec','-T','policy-worker','cat','/tmp/policy-cost.json',check=False)
        (output/'worker-cost-final.json').write_text(cost.stdout if cost.returncode==0 else '{}')
        sources=probe(lab,'export');(output/'sources.json').write_text(json.dumps(sources,indent=2))
        journals=[]
        for device in lab.devices:
            r=lab.run('run','--rm','-T','--no-deps','--entrypoint','cat','device-'+device,'/device/research-events.jsonl')
            records=[dict(json.loads(v),device=device) for v in r.stdout.splitlines()]
            journals.extend(records)
        (output/'agents.json').write_text(json.dumps(journals,indent=2))
        formed=[v for v in journals if v['kind']=='formed'];identities=[(v['device'],v['epoch'],v['sequence']) for v in formed];nonces=[(v['device'],v['profile'],v['nonce']) for v in formed]
        assert len(identities)==len(set(identities)) and len(nonces)==len(set(nonces))
        lab.run('stop')
    source_hashes=json.loads(lab.run('run','--rm','-T','--no-deps','--entrypoint','python','tests','-c',"import hashlib,json;from pathlib import Path;print(json.dumps({p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in ['src/policy/worker.py','src/policy/state.py','src/policy/engine.py']}))").stdout)
    result=dict(experiment_id=lab.project,source_sha=source,source_hashes=source_hashes,variant=variant,experiment_kind='admission_profile' if receiver_profile else 'policy_throughput',project=lab.project,images=images,devices=len(lab.devices),target_hz=2,worker_count=1,requested_seconds=seconds,start_wall=start_wall,end_wall=end_wall,actual_seconds=actual_seconds,stop_reason=reason,before=before,inflight=inflight,after=after,drain_seconds=drain[-1]['elapsed'],drained=after['security']['pending']==0,source_formed=len(formed),nonce_duplicates=0,policy_mode='DRY_RUN',trusted_detector=False,commands=lab.commands,environment=dict(platform=platform.platform(),python=platform.python_version(),cpu=next(v.split(':',1)[1].strip() for v in Path('/proc/cpuinfo').read_text().splitlines() if v.startswith('model name')),memtotal=next(v for v in Path('/proc/meminfo').read_text().splitlines() if v.startswith('MemTotal:'))),exit_code=0)
    (output/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(dict(project=lab.project,variant=variant,inflight_pending=inflight['security']['pending'],drained=result['drained'],stop_reason=reason)))


def main():
    p=argparse.ArgumentParser();p.add_argument('--directory',required=True);p.add_argument('--seconds',type=int,choices=[30,300,900],required=True);p.add_argument('--variant',choices=['baseline','optimized'],required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--receiver-profile',action='store_true');a=p.parse_args();observe(Lab(a.directory),a.seconds,a.output,a.variant,a.receiver_profile)
if __name__=='__main__':main()

"""Bounded implementation benchmark including one-shot Go IPC overhead."""
import argparse,json,os,sys,subprocess,time,statistics,resource,platform
from pathlib import Path
from src.crypto_profiles import ASCON,AES,KUZ,PROFILES,encrypt,decrypt
from src.telemetry import canonical


def child(profile,size,count):
    key=os.urandom(PROFILES[profile]['key_bytes']);aad=canonical(dict(device_id='benchmark',topic='iot/sensors/benchmark',key_epoch=1,sequence_number=1,schema_version=2,profile='equal-length-research-aad'))
    plain=b'x'*size
    def nonce(i):return i.to_bytes(PROFILES[profile]['nonce_bytes'],'big')
    for i in range(1,21):
        ct=encrypt(profile,key,nonce(i),aad,plain);assert decrypt(profile,key,nonce(i),aad,ct)==plain
    start_cpu=time.process_time();start_children=resource.getrusage(resource.RUSAGE_CHILDREN);start=time.perf_counter();enc=[];dec=[]
    for i in range(21,count+21):
        t=time.perf_counter_ns();ct=encrypt(profile,key,nonce(i),aad,plain);enc.append(time.perf_counter_ns()-t)
        t=time.perf_counter_ns();value=decrypt(profile,key,nonce(i),aad,ct);dec.append(time.perf_counter_ns()-t);assert value==plain
    wall=time.perf_counter()-start;end_children=resource.getrusage(resource.RUSAGE_CHILDREN)
    def stats(v):
        ordered=sorted(v)
        return dict(mean=statistics.mean(v),median=statistics.median(v),stdev=statistics.stdev(v),minimum=min(v),maximum=max(v),p95=ordered[int(.95*(len(v)-1))],p99=ordered[int(.99*(len(v)-1))])
    return dict(profile=profile,payload_bytes=size,aad_bytes=len(aad),ciphertext_expansion=len(ct)-len(plain),iterations=count,warmup=20,
        encrypt_ns=stats(enc),authenticated_decrypt_ns=stats(dec),raw_encrypt_ns=enc,raw_decrypt_ns=dec,
        wall_seconds=wall,python_cpu_seconds=time.process_time()-start_cpu,
        child_cpu_seconds=end_children.ru_utime+end_children.ru_stime-start_children.ru_utime-start_children.ru_stime,
        python_peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,provider_child_peak_rss_kib=end_children.ru_maxrss if profile==KUZ else None,
        encrypt_decrypt_pairs_per_second=count/wall)


def main():
    p=argparse.ArgumentParser();p.add_argument('--child');p.add_argument('--size',type=int);p.add_argument('--iterations',type=int,default=300);p.add_argument('--output',type=Path);a=p.parse_args()
    if not 100<=a.iterations<=1000:raise ValueError('Bounded iterations required')
    if a.child:
        if a.child not in PROFILES or not 1<=a.size<=1024:raise ValueError('Bounded profile/size required')
        print(json.dumps(child(a.child,a.size,a.iterations)));return
    if not a.output or a.output.exists():raise ValueError('New report path required')
    real_size=len(canonical(dict(temperature=23.5,humidity=48.0,timestamp='2026-11-12T12:00:00.000000+00:00')));rows=[]
    for repeat in range(3):
        order=[ASCON,AES,KUZ];order=order[repeat:]+order[:repeat]
        for size in [64,256,1024,real_size]:
            for profile in order:
                r=subprocess.run([sys.executable,'-m','scripts.benchmark_stage11','--child',profile,'--size',str(size),'--iterations',str(a.iterations)],capture_output=True,text=True,check=True,timeout=120)
                rows.append(dict(repeat=repeat,**json.loads(r.stdout)))
    report=dict(source_sha=subprocess.check_output(['git','rev-parse','HEAD']).decode().strip(),environment=dict(python=platform.python_version(),platform=platform.platform()),runs=rows,
        limitations=['Implementation comparison: Python reference Ascon, native AES, Go CT Kuz/MGM including process IPC','Three independent process/key runs; within-run packets correlated; no confidence interval claim','p95/p99 descriptive of 300 samples, no stable tail latency claim','x86 software host only; no ARM or certification claim'],exit_code=0)
    a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(runs=len(rows),exit_code=0)))

if __name__=='__main__':main()

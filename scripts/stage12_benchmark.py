"""Sequential fresh-process implementation experiments; no live keys or Magma AEAD."""
import argparse,json,os,time,statistics,subprocess,sys,resource,platform
from pathlib import Path
from src.crypto_profiles import ASCON,AES,KUZ,PROFILES,encrypt,decrypt
from src.telemetry import canonical

IDS=['ascon-python','aes-native','kuz-go-one-shot','kuz-go-worker','kuz-python-research']

def describe(values):
    v=sorted(values)
    return dict(mean=statistics.mean(v),median=statistics.median(v),stdev=statistics.stdev(v),minimum=v[0],maximum=v[-1],p95=v[int(.95*(len(v)-1))],p99=v[int(.99*(len(v)-1))])


def child(impl,size,aad_mode,count,candidate,cpu_scope=False):
    allowed=os.sched_getaffinity(0);os.sched_setaffinity(0,{min(allowed)})
    profile=ASCON if impl=='ascon-python' else AES if impl=='aes-native' else KUZ
    key=os.urandom(PROFILES[profile]['key_bytes']);plain=b'x'*size
    aad=(b'a'*128 if aad_mode=='fixed' else canonical(dict(device_id='alpha',topic='iot/sensors/alpha',key_epoch=1,sequence_number=1,schema_version=2,profile=PROFILES[profile]['algorithm'])))
    setup=[]
    if impl=='kuz-python-research':
        from scripts.python_kuz_research import load,operation
        implementation=load(candidate)
        enc=lambda n:operation(implementation,key,n,aad,plain)
        dec=lambda n,c:operation(implementation,key,n,aad,c,True)
        for _ in range(100):
            t=time.perf_counter_ns();implementation[0](key);setup.append(time.perf_counter_ns()-t)
    else:
        os.environ['LCM_KUZ_BACKEND']='persistent' if impl=='kuz-go-worker' else 'one-shot'
        enc=lambda n:encrypt(profile,key,n,aad,plain)
        dec=lambda n,c:decrypt(profile,key,n,aad,c)
        if impl=='aes-native':
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            for _ in range(100):
                t=time.perf_counter_ns();AESGCM(key);setup.append(time.perf_counter_ns()-t)
    for i in range(1,21):
        n=i.to_bytes(PROFILES[profile]['nonce_bytes'],'big');ct=enc(n);assert dec(n,ct)==plain
    if cpu_scope and impl=='kuz-go-worker':
        from src.kuz_worker import WORKER
        WORKER.close() # Reap warmup children before measuring CPU; next spawn included explicitly.
    before=resource.getrusage(resource.RUSAGE_CHILDREN);start=time.perf_counter();cpu=time.process_time();en=[];de=[]
    for i in range(21,count+21):
        n=i.to_bytes(PROFILES[profile]['nonce_bytes'],'big');t=time.perf_counter_ns();ct=enc(n);en.append(time.perf_counter_ns()-t)
        t=time.perf_counter_ns();value=dec(n,ct);de.append(time.perf_counter_ns()-t);assert value==plain
    elapsed=time.perf_counter()-start;pycpu=time.process_time()-cpu
    if impl=='kuz-go-worker':
        from src.kuz_worker import WORKER
        WORKER.close()  # reap child for accurate RUSAGE_CHILDREN CPU accounting
    after=resource.getrusage(resource.RUSAGE_CHILDREN)
    return dict(implementation=impl,profile=profile,payload_bytes=size,aad_mode=aad_mode,aad_bytes=len(aad),iterations=count,warmup=20,cpu_affinity=sorted(os.sched_getaffinity(0)),encrypt_ns=describe(en),decrypt_ns=describe(de),raw_encrypt_ns=en,raw_decrypt_ns=de,wall_seconds=elapsed,python_cpu_seconds=pycpu,child_cpu_seconds=after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,python_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,child_rss_kib=after.ru_maxrss if impl.startswith('kuz-go') else None,ciphertext_bytes=len(ct),tag_bytes=16,pairs_per_second=count/elapsed,key_setup_ns=describe(setup) if setup else 'not_measured_separately')


def main():
    p=argparse.ArgumentParser();p.add_argument('--child');p.add_argument('--cpu-only',action='store_true');p.add_argument('--size',type=int);p.add_argument('--aad',default='fixed');p.add_argument('--candidate',required=True);p.add_argument('--output',type=Path);p.add_argument('--iterations',type=int,default=1000);a=p.parse_args()
    if a.iterations!=1000:raise ValueError('Predeclared1000 samples required')
    if a.child:
        if a.child not in IDS or a.size not in [64,83,256,1024] or a.aad not in ['fixed','telemetry']:raise ValueError('Bounded matrix')
        print(json.dumps(child(a.child,a.size,a.aad,a.iterations,a.candidate,a.cpu_only)));return
    if not a.output or a.output.exists():raise ValueError('New report path required')
    runs=[]
    for repeat in range(5):
        order=IDS[repeat:]+IDS[:repeat]
        for aad in (['fixed'] if a.cpu_only else ['fixed','telemetry']):
            for size in ([83] if a.cpu_only else [64,83,256,1024]):
                for impl in order:
                    r=subprocess.run([sys.executable,'-m','scripts.stage12_benchmark','--child',impl,'--size',str(size),'--aad',aad,'--candidate',a.candidate]+(['--cpu-only'] if a.cpu_only else []),capture_output=True,text=True,timeout=120,check=True)
                    runs.append(dict(repeat=repeat,**json.loads(r.stdout)))
                    a.output.with_suffix('.partial.json').write_text(json.dumps(runs))
                    a.output.with_suffix('.progress.json').write_text(json.dumps(dict(completed=len(runs),last=dict(repeat=repeat,implementation=impl,payload_bytes=size,aad=aad))))
    report=dict(source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),environment=dict(python=platform.python_version(),platform=platform.platform()),cpu_scope='post-warmup worker reap; measured cold/recycle starts included' if a.cpu_only else 'original worker child CPU includes initial warmup lifetime; do not use for strict CPU comparison',runs=runs,
        interpretation=['Five fresh-process/key runs; no packet-level independence or confidence interval claim','One pinned CPU affinity per process, no cgroup quota on host microbenchmark; same constraint for every backend','Go worker includes recycle/startup every256 requests; no cached keys/cipher context','PyGOST5.12 strict wrapper is research-only, not a live provider','No mathematical algorithm speed/strength or ARM inference'],exit_code=0)
    a.output.write_text(json.dumps(report,indent=2));print(json.dumps(dict(runs=len(runs),exit_code=0)))

if __name__=='__main__':main()

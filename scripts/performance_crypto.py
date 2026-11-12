"""Stage10 independent-process implementation benchmark; never production keys."""
import argparse,csv,json,os,platform,resource,statistics,subprocess,sys,time
from pathlib import Path
import cryptography
from cryptography.hazmat.backends.openssl.backend import backend
from src.crypto_profiles import ASCON,AES,PROFILES,encrypt,decrypt
from src.telemetry import canonical


def child(profile,size,n):
    key=os.urandom(16);aad=b'a'*148;pt=b'x'*size
    enc=[];dec=[];begin=time.process_time_ns()
    for i in range(n+100):
        nonce=i.to_bytes(PROFILES[profile]['nonce_bytes'],'big')
        t=time.perf_counter_ns();ct=encrypt(profile,key,nonce,aad,pt);e=time.perf_counter_ns()-t
        t=time.perf_counter_ns();plain=decrypt(profile,key,nonce,aad,ct);d=time.perf_counter_ns()-t
        assert plain==pt
        if i>=100:enc.append(e);dec.append(d)
    return dict(profile=profile,size=size,aad_bytes=len(aad),warmup=100,encrypt_ns=enc,decrypt_ns=dec,ciphertext_bytes=len(ct),cpu_ns=time.process_time_ns()-begin,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)


def main():
    p=argparse.ArgumentParser();p.add_argument('--child');p.add_argument('--size',type=int);p.add_argument('--samples',type=int,default=1000);p.add_argument('--output',type=Path);a=p.parse_args()
    if not 1000<=a.samples<=5000:p.error('1000..5000 samples required')
    if a.child:
        if a.child not in PROFILES or a.size not in [64,256,1024,83]:p.error('Bounded benchmark')
        print(json.dumps(child(a.child,a.size,a.samples)));return
    if a.output.exists():p.error('Immutable output exists')
    real=len(canonical(dict(temperature=23.5,humidity=48.0,timestamp='2026-11-12T00:00:00.123456+00:00')))
    # Match canonical actual software-agent plaintext length, never synthetic E2E.
    assert real==83,real
    runs=[]
    for repeat in range(3):
        for size in [64,256,1024,real]:
            for profile in ([ASCON,AES] if repeat%2==0 else [AES,ASCON]):
                r=subprocess.run([sys.executable,'-m','scripts.performance_crypto','--child',profile,'--size',str(size),'--samples',str(a.samples)],capture_output=True,text=True,check=True,timeout=90)
                run=dict(repeat=repeat,**json.loads(r.stdout))
                run['summary']={}
                for field in ['encrypt_ns','decrypt_ns']:
                    v=sorted(run[field]);run['summary'][field]=dict(mean=statistics.mean(v),median=statistics.median(v),stddev=statistics.stdev(v),p95=v[int((len(v)-1)*.95)],p99=v[int((len(v)-1)*.99)],min=v[0],max=v[-1],throughput_bytes_second=size*1e9/statistics.mean(v))
                runs.append(run)
    result=dict(git_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),platform=platform.platform(),python=platform.python_version(),cryptography=cryptography.__version__,openssl=backend.openssl_version_text(),real_plaintext_bytes=real,runs=runs,exit_code=0,limitations=['Implementation comparison: Python Ascon reference vs native cryptography AESGCM','Three independent process runs; per-packet tails are conditional, no packet pseudo-replication CI','Peak RSS is whole process, not allocation of one cipher','Shared host background services remain active'])
    a.output.write_text(json.dumps(result,indent=2))
    with a.output.with_suffix('.csv').open('w') as f:
        w=csv.writer(f);w.writerow(['repeat','profile','size','operation','index','nanoseconds'])
        for r in runs:
            for op in ['encrypt_ns','decrypt_ns']:
                for i,t in enumerate(r[op]):w.writerow([r['repeat'],r['profile'],r['size'],op,i,t])
    print('24 independent process series complete; exit 0')

if __name__=='__main__':main()

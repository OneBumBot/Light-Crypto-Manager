"""Bounded software AEAD benchmark, no claim of algorithm strength or ARM speed."""
import argparse,json,time,statistics,resource,platform,subprocess,sys,os
from pathlib import Path
import cryptography
from cryptography.hazmat.backends.openssl.backend import backend
from src.crypto_profiles import ASCON,AES,encrypt,decrypt,PROFILES


def percentile(values,p):
    values=sorted(values);return values[min(len(values)-1,int((len(values)-1)*p))]


def child(profile,size,iterations):
    key=os.urandom(16);ad=b'benchmark-device-bound-aad';pt=b'x'*size
    def nonce(i):return i.to_bytes(PROFILES[profile]['nonce_bytes'],'big')
    for i in range(1,21):
        ct=encrypt(profile,key,nonce(i),ad,pt);assert decrypt(profile,key,nonce(i),ad,ct)==pt
    enc=[];dec=[];cpu=time.process_time();wall=time.perf_counter()
    for i in range(21,iterations+21):
        start=time.perf_counter_ns();ct=encrypt(profile,key,nonce(i),ad,pt);enc.append(time.perf_counter_ns()-start)
        start=time.perf_counter_ns();plain=decrypt(profile,key,nonce(i),ad,ct);dec.append(time.perf_counter_ns()-start);assert plain==pt
    cpu=time.process_time()-cpu;wall=time.perf_counter()-wall
    # Each child uses a fresh process and fresh ephemeral benchmark key; production nonces/keys are never used.
    return dict(profile=profile,payload_bytes=size,ciphertext_bytes=len(ct),aad_bytes=len(ad),iterations=iterations,warmup=20,
                encryption_us={k:percentile(enc,p)/1000 for k,p in [('p50',.5),('p95',.95),('p99',.99)]},
                authenticated_decryption_us={k:percentile(dec,p)/1000 for k,p in [('p50',.5),('p95',.95),('p99',.99)]},
                cpu_seconds=cpu,wall_seconds=wall,cpu_percent_of_one_core=cpu/wall*100,paired_encrypt_decrypt_per_second=iterations/wall,
                peak_process_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)


def main():
    p=argparse.ArgumentParser();p.add_argument('--child');p.add_argument('--size',type=int,default=256);p.add_argument('--iterations',type=int,default=300);p.add_argument('--output',type=Path)
    a=p.parse_args()
    if not 20<=a.iterations<=1000 or not 1<=a.size<=2048:p.error('Bounded benchmark required')
    if a.child:print(json.dumps(child(a.child,a.size,a.iterations)));return
    runs=[]
    for repeat in range(3):
        order=[ASCON,AES] if repeat%2==0 else [AES,ASCON]
        for size in [64,256,1024]:
            for profile in order:
                r=subprocess.run([sys.executable,'-m','scripts.crypto_benchmark','--child',profile,'--size',str(size),'--iterations',str(a.iterations)],check=True,capture_output=True,text=True,timeout=45)
                runs.append(dict(repeat=repeat,**json.loads(r.stdout)))
    result=dict(schema_version=1,python=platform.python_version(),architecture=platform.machine(),platform=platform.platform(),cryptography=cryptography.__version__,openssl=backend.openssl_version_text(),cpu_count=os.cpu_count(),
        measurements=runs,limitations=['Ascon pure Python reference vs native optimized AESGCM: implementation comparison, not pure algorithm comparison','No separate authentication-only timing; decrypt includes AEAD verification','Software x86/host measurements, not Raspberry Pi/ARM or energy','Container CPU/RAM limits and background load documented separately','Ephemeral benchmark keys, no production telemetry/model training'])
    if a.output:
        if a.output.exists():raise ValueError('Immutable benchmark report already exists')
        a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()

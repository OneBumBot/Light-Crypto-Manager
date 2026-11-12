"""Direct native, startup+reject and noncrypto IPC measurements; no subtraction."""
import argparse,json,subprocess,os,time,struct,statistics,math
from pathlib import Path


def main():
 p=argparse.ArgumentParser();p.add_argument('--measure',required=True);p.add_argument('--original',required=True);p.add_argument('--optimized',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():raise ValueError('Immutable output')
 os.sched_setaffinity(0,{min(os.sched_getaffinity(0))});runs=[]
 for repeat in range(5):
  data=json.loads(subprocess.check_output([a.measure],text=True,timeout=30))
  x,y=data['fixed_class_ns'],data['random_class_ns'];den=math.sqrt(statistics.variance(x)/len(x)+statistics.variance(y)/len(y));data['welch_t_descriptive']=(statistics.mean(x)-statistics.mean(y))/den if den else None
  for field,path in [('startup_original_ns',a.original),('startup_optimized_ns',a.optimized)]:
   values=[]
   for _ in range(100):
    t=time.perf_counter_ns();r=subprocess.run([path],input=b'',capture_output=True,timeout=5);values.append(time.perf_counter_ns()-t);assert r.stdout==b'\2' and r.returncode==0
   data[field]=values
  child=subprocess.Popen([a.measure,'echo'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
  values=[];frame=struct.pack('!I',83)+b'x'*83
  for _ in range(1000):
   t=time.perf_counter_ns();child.stdin.write(frame);child.stdin.flush();head=child.stdout.read(4);assert head==frame[:4];body=child.stdout.read(83);assert body==frame[4:];values.append(time.perf_counter_ns()-t)
  child.stdin.close();assert child.wait(timeout=2)==0;child.stdout.close();data['echo_roundtrip_ns']=values;data['repeat']=repeat;runs.append(data)
 report=dict(runs=runs,interpretation=['Direct native context reused sequentially; setup separately timed','Startup includes empty-input rejection and pipe IO; not approximate pure startup','Echo instrumentation is not cryptography and is not shipped in runtime','Welch values descriptive screening only: correlated samples, scheduling/GC and no constant-time proof'],exit_code=0)
 a.output.write_text(json.dumps(report,indent=2));print('Five native/IPC/timing-class runs: exit0')

if __name__=='__main__':main()

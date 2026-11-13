"""Bounded actual Stage15 runs. Reports counters by unit, never telemetry==TCP packet."""
import argparse,json,os,subprocess,time
from pathlib import Path
from scripts.stage15_setup import lab
from src.shadow_ids.parity import compare
from src.shadow_ids.journal import Journal
from src.research_stand.config import Experiment

def send(l,args,value):
 r=subprocess.run(l.base+args,input=json.dumps(value),capture_output=True,text=True,timeout=90)
 if r.returncode:raise RuntimeError('Stage15 stdin operation failed (private diagnostics required)')
 return r.stdout

def workload(l,name,clients,interval,duration=15,scenario='regular',seed=1500,violation=False):
 config=dict(experiment_id=name,scenario=scenario,clients=clients,duration=duration,interval=interval,jitter=.05,seed=seed,violation=violation,schema_version=1)
 send(l,['exec','-T','lab-devices','python','-c',"import sys;from pathlib import Path;Path('/research/stage15-config.json').write_text(sys.stdin.read())"],config)
 l.run('exec','-T','lab-devices','python','-m','scripts.stage15_workload','--config','/research/stage15-config.json',timeout=duration+30)
 truth=json.loads(l.run('exec','-T','lab-devices','cat','/research/'+name+'/ground-truth.json').stdout)
 return truth

def capture(l,name,condition='capture',duration=22):
 root=l.root/'shadow'/name
 if root.exists():raise ValueError('Previous run preserved')
 args=['run','-d','--no-deps','--name',l.project+'-'+name+'-capture','shadow-network-observer','python','-m','src.shadow_ids.capture','--root','/shadow/'+name,'--duration',str(duration)]
 if condition=='capture':args+=['--extract-only']
 cid=l.run(*args).stdout.strip().splitlines()[-1];deadline=time.monotonic()+10
 while time.monotonic()<deadline:
  if (root/'traffic.pcap').exists() and (root/'traffic.pcap').stat().st_size>=24:return cid
  r=subprocess.run(['docker','inspect',cid,'--format','{{.State.Running}}'],capture_output=True,text=True)
  if r.stdout.strip()=='false':raise RuntimeError('Actual capture process failed before ready')
  time.sleep(.1)
 raise TimeoutError('Capture readiness watchdog')

def wait(cid):
 r=subprocess.run(['docker','wait',cid],capture_output=True,text=True,timeout=90)
 if r.returncode or r.stdout.strip()!='0':raise RuntimeError('Stage15 capture/worker exit not0')

def main():
 p=argparse.ArgumentParser();p.add_argument('action',choices=['parity']);p.add_argument('--directory',type=Path,default=Path('.local-runtime/stage15/online'));p.add_argument('--prefix',default='parity');p.add_argument('--output',type=Path,default=Path('docs/reports/stage15/feature-parity.json'));a=p.parse_args();l=lab(a.directory);reports=Path('docs/reports/stage15');results=[]
 if a.output.exists():raise ValueError('Immutable parity report')
 for n in range(3):
  name=f'{a.prefix}-{n:02}';cid=capture(l,name);truth=workload(l,name,3,.5,seed=1500+n);wait(cid);l.run('run','--rm','--no-deps','--user',str(os.getuid())+':'+str(os.getgid()),'-v',str(l.root/'shadow'/name)+':/parity','traffic-collector','python','-m','src.research_stand.collector','extract','--directory','/parity');r=compare(l.root/'shadow'/name);r.update(run=name,formed_or_sent=truth['sent_messages'],generator_errors=truth['errors']);results.append(r);print(name,r['status'],r['physical_packets'],flush=True)
 report=dict(status='PASS' if all(r['status']=='PASS' for r in results) else 'BLOCKED',feature_version='tcp-packet-passive-v1',parser_sha256=results[0]['parser_sha256'],integral_mismatches=sum(r['integral_mismatches'] for r in results),delta_mismatches=sum(r['delta_mismatches'] for r in results),supported_packets=sum(r['supported_packets'] for r in results),runs=results,source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),exit_code=0 if all(r['status']=='PASS' for r in results) else 2)
 a.output.write_text(json.dumps(report,indent=2));(l.root/'parity.json').write_text(json.dumps(report));raise SystemExit(report['exit_code'])
if __name__=='__main__':main()

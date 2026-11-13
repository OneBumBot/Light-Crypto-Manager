"""Sequential preregistered fresh broker realms. No training; no old-state reset."""
import argparse,json,subprocess,time
from pathlib import Path
from scripts.stage14_lab import Lab,prepare
from scripts.stage14_collect import collect
from src.research_stand.stage14 import checked_collection_plan


def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('.local-runtime/stage14'));p.add_argument('--reports',type=Path,default=Path('docs/reports/stage14'));a=p.parse_args();plan=checked_collection_plan(a.reports/'collection-plan.json');deadline=time.monotonic()+5400
 Lab(a.root/'pilot').stop()
 running=subprocess.check_output(['docker','ps','--filter','label=com.docker.compose.service=lab-devices','--format','{{.Names}}'],text=True).splitlines()
 if running:raise ValueError('Stop other research generators before collection')
 refs={k:subprocess.check_output(['docker','image','inspect','lcm-stage14-ground-truth-pilot-'+k,'--format','{{.Id}}'],text=True).strip() for k in ['runtime','tests','laboratory']}
 results=[]
 for block in range(30):
  if time.monotonic()>deadline:raise TimeoutError('Stage14 overall collection watchdog; retained sources, no training')
  group=f'block-{block:02}';report=a.reports/(group+'-acquisition.json');directory=a.root/group;project='lcm-stage14-ground-truth-'+group
  if report.exists():
   saved=json.loads(report.read_text());assert saved['plan_sha256']==plan['sha256'];results.append(saved);continue
  if directory.exists():raise ValueError('Partial prior acquisition needs reviewed continuation, never implicit reset')
  prepare(directory,project,'10.214.'+str(10+block)+'.0/24')
  for kind,ref in refs.items():subprocess.run(['docker','tag',ref,project+'-'+kind],check=True)
  lab=Lab(directory)
  try:
   subprocess.run(['.venv/bin/python','-m','scripts.stage14_lab','start','--directory',str(directory)],check=True,timeout=300)
   selected=[r for r in plan['primary'] if r['group']==group]
   records=collect(directory,a.root/'primary-captures',[r['config'] for r in selected],plan['sha256'],group,selected[0]['partition'])
   result=dict(group=group,project=project,records=records,plan_sha256=plan['sha256'],status='complete' if all(r['status']=='complete' for r in records) else 'quarantined',commands=lab.commands,exit_code=0 if all(r['status']=='complete' for r in records) else 2)
   report.write_text(json.dumps(result,indent=2));results.append(result)
  finally:lab.stop()
  print(group,'retained, stopped',flush=True)
 (a.reports/'primary-acquisition.json').write_text(json.dumps(dict(plan_sha256=plan['sha256'],blocks=results,training='NOT_EXECUTED_UNTIL_GATE',exit_code=0),indent=2))
if __name__=='__main__':main()

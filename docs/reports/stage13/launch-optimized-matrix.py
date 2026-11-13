import subprocess,time,json
from pathlib import Path
from scripts.policy_lab import Lab
from scripts.policy13_run import observe
root=Path('.local-runtime/stage13');report=Path('docs/reports/stage13');deadline=time.monotonic()+3600
while not (report/'baseline50r1/result.json').exists():
    if time.monotonic()>deadline:raise TimeoutError('Baseline matrix watchdog')
    time.sleep(10)
for cohort,repeat,seconds in [(3,1,300),(10,1,300),(25,1,300),(25,2,300),(25,3,300),(25,4,900),(50,1,300)]:
    name=f'optimized{cohort}r{repeat}';directory=root/name;project='lcm-stage13-policy-'+f'o{cohort}r{repeat}'
    subprocess.run(['.venv/bin/python','-m','scripts.policy_lab','prepare','--directory',str(directory),'--project',project,'--devices',str(cohort)],check=True)
    for target,ref in [('runtime','lcm-stage13-policy-optimized-reference'),('tests','lcm-stage13-policy-optimized-reference-tests')]:subprocess.run(['docker','tag',ref,project+'-'+target],check=True)
    subprocess.run(['.venv/bin/python','-m','scripts.policy_lab','start','--directory',str(directory)],check=True)
    observe(Lab(directory),seconds,report/name,'optimized')

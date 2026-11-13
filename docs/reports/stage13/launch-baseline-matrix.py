import subprocess,json
from pathlib import Path
from scripts.policy_lab import Lab
from scripts.policy13_run import observe
root=Path('.local-runtime/stage13');report=Path('docs/reports/stage13')
base=Lab(root/'baseline3')
for cohort,repeat,seconds in [(3,1,300),(10,1,300),(25,1,300),(25,2,300),(25,3,300),(50,1,300)]:
    name=f'baseline{cohort}r{repeat}';directory=root/name;project='lcm-stage13-policy-'+f'b{cohort}r{repeat}'
    if cohort==3 and repeat==1:lab=base
    else:
        subprocess.run(['.venv/bin/python','-m','scripts.policy_lab','prepare','--directory',str(directory),'--project',project,'--devices',str(cohort)],check=True)
        for target in ['runtime','tests']:subprocess.run(['docker','tag',base.project+'-'+target,project+'-'+target],check=True)
        subprocess.run(['.venv/bin/python','-m','scripts.policy_lab','start','--directory',str(directory)],check=True)
        lab=Lab(directory)
    observe(lab,seconds,report/name,'baseline')

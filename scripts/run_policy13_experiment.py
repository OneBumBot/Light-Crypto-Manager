"""Reproducible fresh single-cohort entrypoint; refuses concurrent Stage13 publishers."""
import argparse,json,subprocess
from pathlib import Path
from scripts.policy_lab import Lab,prepare
from scripts.policy13_run import observe


def main():
    p=argparse.ArgumentParser();p.add_argument('--variant',choices=['baseline','optimized'],required=True);p.add_argument('--devices',type=int,choices=[3,10,25,50],required=True);p.add_argument('--seconds',type=int,choices=[30,300,900],required=True);p.add_argument('--repeat',type=int,choices=[1,2,3,4],default=1);p.add_argument('--runtime-image',required=True);p.add_argument('--tests-image',required=True);p.add_argument('--directory',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--project',required=True);a=p.parse_args()
    if a.output.exists():p.error('Immutable report exists')
    running=subprocess.check_output(['docker','ps','--filter','label=com.docker.compose.service=device-alpha','--format','{{.Names}}'],text=True).splitlines()
    if any(v.startswith('lcm-stage13-policy-') for v in running):p.error('Stop the other Stage13 cohort first; never reset state')
    images={kind:subprocess.check_output(['docker','image','inspect',ref,'--format','{{.Id}}'],text=True).strip() for kind,ref in [('runtime',a.runtime_image),('tests',a.tests_image)]}
    prepare(a.directory,a.project,a.devices)
    for kind,identity in images.items():subprocess.run(['docker','tag',identity,a.project+'-'+kind],check=True)
    subprocess.run(['.venv/bin/python','-m','scripts.policy_lab','start','--directory',str(a.directory)],check=True)
    observe(Lab(a.directory),a.seconds,a.output,a.variant)
if __name__=='__main__':main()

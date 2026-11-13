"""Census only stopped Stage13 performance projects, retaining their volumes/state."""
import argparse,json,subprocess,hashlib
from pathlib import Path
from scripts.policy_lab import Lab


def main():
    p=argparse.ArgumentParser();p.add_argument('--reports',type=Path,default=Path('docs/reports/stage13'));p.add_argument('--root',type=Path,default=Path('.local-runtime/stage13'));a=p.parse_args()
    folders={json.loads(f.read_text())['project']:f.parent for f in a.root.glob('*/stage13.json')}
    for f in sorted(a.reports.glob('*r*/result.json')):
        result=json.loads(f.read_text());out=f.parent/'ledger-final.json'
        if out.exists() or out.with_suffix('.json.gz').exists():continue
        lab=Lab(folders[result['project']]);running=lab.run('ps','-q').stdout.split()
        if running:raise ValueError('Stop every cohort before census')
        try:
            lab.run('up','-d','--no-deps','--wait','postgres','mongo')
            script=Path('scripts/policy13_ledger_probe.py').resolve()
            r=lab.run('run','--rm','-T','--no-deps','-v',str(script)+':/app/scripts/policy13_ledger_probe.py:ro','--entrypoint','python','tests','-m','scripts.policy13_ledger_probe',timeout=120)
            data=json.loads(r.stdout);data.update(project=lab.project,source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),controller_source_hashes=result['source_hashes'])
            out.write_text(json.dumps(data,indent=2))
            environment=lab.probe('environment');(f.parent/'environment.json').write_text(json.dumps(environment,indent=2))
            plans=lab.probe('policy-diagnostics');(f.parent/'actual-policy-plan.json').write_text(json.dumps(plans,indent=2))
        finally:lab.run('stop','postgres','mongo')
        (f.parent/'census-commands.json').write_text(json.dumps(lab.commands,indent=2));print(lab.project,'census exit0',flush=True)
if __name__=='__main__':main()

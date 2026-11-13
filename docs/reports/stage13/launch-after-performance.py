import subprocess,time,json
from pathlib import Path
from scripts.policy_lab import Lab,prepare
from scripts.policy13_run import observe
root=Path('.local-runtime/stage13');reports=Path('docs/reports/stage13');deadline=time.monotonic()+5400
while not (reports/'optimized50r1/result.json').exists():
    if time.monotonic()>deadline:raise TimeoutError('Performance completion watchdog')
    time.sleep(10)
# Distinct short-run series for actual transaction wall/commit timing.
for repeat in range(1,4):
    for variant in (['baseline','optimized'] if repeat%2 else ['optimized','baseline']):
        key=('b' if variant=='baseline' else 'o')+'a25r'+str(repeat);name='admission-'+variant+'25r'+str(repeat);directory=root/name;project='lcm-stage13-policy-'+key
        prepare(directory,project,25)
        prefix='lcm-stage13-policy-base3' if variant=='baseline' else 'lcm-stage13-policy-optimized-reference'
        for kind in ['runtime','tests']:
            ref=prefix+'-'+kind if variant=='baseline' else prefix if kind=='runtime' else prefix+'-tests'
            subprocess.run(['docker','tag',ref,project+'-'+kind],check=True)
        subprocess.run(['.venv/bin/python','-m','scripts.policy_lab','start','--directory',str(directory)],check=True)
        observe(Lab(directory),30,reports/name,variant,receiver_profile=True)
subprocess.run(['.venv/bin/python','-m','scripts.policy13_collect_runs'],check=True)
# This is the first additional active cohort, after all load stands are stopped.
subprocess.run(['.venv/bin/python','-m','scripts.policy13_crypto_lab','start','--directory',str(root/'crypto'),'--build'],check=True)
subprocess.run(['.venv/bin/python','-m','scripts.policy13_reliability','--directory',str(root/'crypto'),'--output',str(reports/'policy-reliability.json')],check=True)
(reports/'policy-reliability-complete.json').write_text(json.dumps({'exit_code':0,'crypto_lab_running_for_next_bounded_checks':True}))

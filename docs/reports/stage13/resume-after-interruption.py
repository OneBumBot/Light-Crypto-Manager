import subprocess,json
from pathlib import Path
from scripts.policy_lab import Lab,prepare
from scripts.policy13_run import observe
root=Path('.local-runtime/stage13');reports=Path('docs/reports/stage13')
for directory in ['admission-baseline25r3','admission-baseline25r3-resumed','qa']:
    lab=Lab(root/directory);lab.run('stop')
(reports/'admission-baseline25r3/interrupted.json').write_text(json.dumps({'status':'interrupted_by_operator','exit_code':130,'included_in_comparison':False,'state_retained':True},indent=2))
for variant in ['baseline','optimized']:
    name='admission-'+variant+'25r3-final';directory=root/name;project='lcm-stage13-policy-'+('ba25r3final' if variant=='baseline' else 'oa25r3final')
    if not directory.exists():prepare(directory,project,25)
    config_path=directory/"policy.compose.json";config=json.loads(config_path.read_text());config["networks"]={"default":{"ipam":{"config":[{"subnet":"10.213."+("4" if variant=="baseline" else "5")+".0/24"}]}}};config_path.write_text(json.dumps(config,indent=2));config_path.chmod(0o600)
    prefix='lcm-stage13-policy-base3' if variant=='baseline' else 'lcm-stage13-policy-optimized-reference'
    for kind in ['runtime','tests']:
        ref=prefix+'-'+kind if variant=='baseline' else prefix if kind=='runtime' else prefix+'-tests'
        subprocess.run(['docker','tag',ref,project+'-'+kind],check=True)
    subprocess.run(['.venv/bin/python','-m','scripts.policy_lab','start','--directory',str(directory)],check=True)
    observe(Lab(directory),30,reports/name,variant,receiver_profile=True)
subprocess.run(['.venv/bin/python','-m','scripts.policy13_collect_runs'],check=True)
subprocess.run(['.venv/bin/python','-m','scripts.policy13_analyze'],check=True)
config_path=root/'crypto/research.compose.json';config=json.loads(config_path.read_text());config['networks']={'default':{'ipam':{'config':[{'subnet':'10.213.3.0/24'}]}}};config_path.write_text(json.dumps(config,indent=2));config_path.chmod(0o600)
subprocess.run(['.venv/bin/python','-m','scripts.policy13_crypto_lab','start','--directory',str(root/'crypto'),'--build'],check=True)
subprocess.run(['.venv/bin/python','-m','scripts.policy13_reliability','--directory',str(root/'crypto'),'--output',str(reports/'policy-reliability.json')],check=True)
(reports/'policy-reliability-complete.json').write_text(json.dumps({'exit_code':0,'crypto_lab_running_for_next_bounded_checks':True}))
subprocess.run(['.venv/bin/python','-m','scripts.policy13_crypto_checks','--directory',str(root/'crypto'),'--reports',str(reports)],check=True)

import subprocess,time
from pathlib import Path
reports=Path('docs/reports/stage13');deadline=time.monotonic()+7200
while not (reports/'policy-reliability-complete.json').exists():
    if time.monotonic()>deadline:raise TimeoutError('Policy recovery phase watchdog')
    time.sleep(10)
subprocess.run(['.venv/bin/python','-m','scripts.policy13_crypto_checks','--directory','.local-runtime/stage13/crypto','--reports',str(reports)],check=True)

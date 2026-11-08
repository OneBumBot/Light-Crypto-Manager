"""Install generated files into role-specific volumes, never into images."""
import json
import os
from pathlib import Path
import shutil

source = Path('/input')
for role in ['broker','publisher','receiver','web','smoke','tests']:
    target = Path('/out')/role
    uid = 1883 if role == 'broker' else 10001
    target.mkdir(exist_ok=True)
    target.chmod(0o700)
    os.chown(target, uid, uid)
    files = ['ca.crt']
    if role == 'broker':
        files += ['server.crt','server.key','passwords','monitor.password']
    elif role == 'tests':
        files += [name+'.password' for name in ['publisher','receiver','web','smoke','monitor']]
        files += ['registry.json','untrusted.crt']
    else:
        files += [role+'.password']
    for name in files:
        path = target/name
        shutil.copyfile(source/name,path)
        path.chmod(0o600)
        os.chown(path,uid,uid)
    if role == 'broker':
        path=target/'health.conf'
        password=(source/'monitor.password').read_text().strip()
        path.write_text('-h localhost\n-p 8883\n--cafile /mosquitto/security/ca.crt\n-u monitor\n-P '+password+'\n-t lightcrypto/health\n-m ping\n-q 1\n')
        path.chmod(0o600)
        os.chown(path,uid,uid)
    if role in ['publisher','receiver','web','smoke']:
        registry=json.loads((source/'registry.json').read_text())
        if role in ['publisher','smoke']:
            name = 'raspb1' if role=='publisher' else 'smoke'
            registry={name:registry[name]}
        path=target/'registry.json'
        path.write_text(json.dumps(registry))
        path.chmod(0o600)
        os.chown(path,uid,uid)
# Publisher counters and smoke counters must survive container replacement.
for role in ['publisher-state','smoke-state']:
    path=Path('/out')/role
    path.chmod(0o700)
    os.chown(path,10001,10001)
print('Role-specific security volumes installed')

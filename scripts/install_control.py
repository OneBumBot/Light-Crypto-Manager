"""Install ONLY isolated preprovisioned control volumes; no secrets in image."""
import os,shutil
from pathlib import Path
root=Path('/input');out=Path('/out')
for device in ['alpha','beta','gamma']:
    target=out/device;target.mkdir(exist_ok=True);target.chmod(0o700);os.chown(target,10001,10001)
    if (target/'installed').exists() and not (target/'device.db').exists():raise ValueError('Missing device state; recovery required, refusing reinitialization')
    # Device state may never be reset by restart of init service.
    for src in (root/device).iterdir():
        if src.name.endswith('.lock'):continue
        dest=target/src.name
        if src.name=='device.db' and dest.exists():continue
        shutil.copyfile(src,dest);dest.chmod(0o600);os.chown(dest,10001,10001)
    marker=target/'installed';marker.touch();marker.chmod(0o600);os.chown(marker,10001,10001)
controller=out/'controller';controller.mkdir(exist_ok=True);controller.chmod(0o700);os.chown(controller,10001,10001)
for source,name in [(root/'control.json','control.json'),(root/'mqtt/controller.password','controller.password'),(root/'mqtt/ca.crt','ca.crt')]:
    dest=controller/name;shutil.copyfile(source,dest);dest.chmod(0o600);os.chown(dest,10001,10001)
print('Scoped live-control volumes installed; existing state preserved')

"""Stage13-only provisioning; preserves every existing device SQLite and marker."""
import json,os,shutil,re
from pathlib import Path
root=Path('/input');identity=json.loads((root/'stage12.json').read_text())
if not re.fullmatch(r'lcm-stage13-policy-[a-z0-9-]{1,18}',identity['project']):raise ValueError('Stage13 only')
for device in identity['devices']:
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,47}',device):raise ValueError('Device identity')
    target=Path('/out')/device;target.mkdir(exist_ok=True);target.chmod(0o700);os.chown(target,10001,10001)
    if (target/'installed').exists() and not (target/'device.db').exists():raise ValueError('Missing used device state; no reset')
    for source in (root/device).iterdir():
        if source.name.endswith('.lock'):continue
        dest=target/source.name
        if source.name=='device.db' and dest.exists():continue
        shutil.copyfile(source,dest);dest.chmod(0o600);os.chown(dest,10001,10001)
    marker=target/'installed';marker.touch();marker.chmod(0o600);os.chown(marker,10001,10001)
controller=Path('/out/controller');controller.mkdir(exist_ok=True);controller.chmod(0o700);os.chown(controller,10001,10001)
for source,name in [(root/'control.json','control.json'),(root/'mqtt/controller.password','controller.password'),(root/'mqtt/ca.crt','ca.crt')]:
    dest=controller/name;shutil.copyfile(source,dest);dest.chmod(0o600);os.chown(dest,10001,10001)
print('Independent device/control volumes installed; existing authority preserved')

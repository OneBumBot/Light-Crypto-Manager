"""Fresh preprovisioned live-control material. Never modifies an existing lab."""
import argparse,os,json,secrets,subprocess
from pathlib import Path
from src.device_control.state import DeviceState
from src.crypto_profiles import ASCON,AES


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',type=Path,required=True);p.add_argument('--project',required=True)
    a=p.parse_args()
    import re
    if not re.fullmatch(r'lcm-stage8-[a-z0-9-]{1,24}',a.project):p.error('Isolated stage8 project required')
    prepare(a.directory, a.project)


def prepare(directory, project):
    import re
    if not re.fullmatch(r'lcm-(?:stage8-|stage9-demo-)[a-z0-9-]{1,24}', project):
        raise ValueError('Isolated control project required')
    os.umask(0o077);root=Path(directory).resolve();root.mkdir(parents=True,mode=0o700,exist_ok=False)
    subprocess.run(['python3','scripts/prepare_compose.py','--env-file',str(root/'compose.env'),'--project',project,'--mqtt-port','0','--web-port','0'],check=True)
    subprocess.run(['python3','scripts/prepare_security.py','--directory',str(root/'mqtt'),'--extra-device','alpha','--extra-device','beta','--extra-device','gamma'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    subprocess.run(['python3','scripts/prepare_storage.py','--directory',str(root/'mongo')],check=True)
    registry=json.loads((root/'mqtt/registry.json').read_text());control={}
    for device in ['alpha','beta','gamma']:
        registry[device]['telemetry_keys']={'AES-128-GCM':secrets.token_hex(16)}
        control[device]=dict(registry=registry[device],command_key=secrets.token_hex(32),status_key=secrets.token_hex(32),capabilities=[ASCON,AES] if device!='gamma' else [ASCON],command_epoch=1)
        d=root/device;d.mkdir(mode=0o700)
        (d/'control.json').write_text(json.dumps({device:control[device]}))
        (d/'registry.json').write_text(json.dumps({device:registry[device]}))
        for name in ['ca.crt','device_'+device+'.password']:(d/name).write_bytes((root/'mqtt'/name).read_bytes())
        state=DeviceState(d/'device.db',device,1,initialize=True);state.close()
    (root/'mqtt/registry.json').write_text(json.dumps(registry))
    (root/'control.json').write_text(json.dumps(control))
    controller=secrets.token_hex(24);(root/'mqtt/controller.password').write_text(controller+'\n')
    from scripts.prepare_security import BROKER_IMAGE
    subprocess.run(['docker','run','--rm','-i','--user',f'{os.getuid()}:{os.getgid()}','--mount',f'type=bind,source={root / "mqtt"},target=/work','--entrypoint','mosquitto_passwd',BROKER_IMAGE,'/work/passwords','controller'],input=(controller+'\n'+controller+'\n').encode(),check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    for f in root.rglob('*'):
        if f.is_file():f.chmod(0o600)
    env=(root/'compose.env').read_text().replace('MQTT_SECURITY_DIR=.local-runtime/security','MQTT_SECURITY_DIR='+str(root/'mqtt')).replace('MONGO_SECURITY_DIR=.local-runtime/mongo-security','MONGO_SECURITY_DIR='+str(root/'mongo'))
    env+='\nCONTROL_INPUT_DIR='+str(root)+'\nCONTROL_MODE=MANUAL_AUTHORIZED_CONTROL\n'
    (root/'compose.env').write_text(env)
    print('Independent control provisioning complete; values withheld')

if __name__=='__main__':main()

"""Generate local CA/server certificates, per-role passwords and per-device keys."""
import argparse
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import subprocess

BROKER_IMAGE = 'eclipse-mosquitto:2@sha256:75d6662dee52c947dc9dd9c29f1d8d7ffef78ddaf38001caa09755681e8bbc98'
ROLES = ['publisher', 'receiver', 'web', 'smoke', 'monitor']


def run(command, **kwargs):
    subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--server-name', action='append', default=[])
    parser.add_argument('--server-ip', action='append', default=[])
    parser.add_argument('--extra-device', action='append', default=[])
    args = parser.parse_args()
    if len(set(args.extra_device)) != len(args.extra_device) or any(not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,47}', name) or name in ['raspb1','smoke'] for name in args.extra_device):
        parser.error('Invalid or duplicate device identity')
    names = ['broker', 'localhost'] + args.server_name
    if any(not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]{0,252}', name) for name in names):
        parser.error('Invalid DNS name')
    ips = ['127.0.0.1'] + [str(ipaddress.ip_address(value)) for value in args.server_ip]
    directory = args.directory.resolve()
    os.umask(0o077)
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    def openssl(*parts):
        run(['openssl', *parts], cwd=directory)
    openssl('req', '-x509', '-newkey', 'rsa:3072', '-nodes', '-keyout', 'ca.key',
            '-out', 'ca.crt', '-days', '30', '-subj', '/CN=LightCrypto Local Test CA',
            '-addext', 'basicConstraints=critical,CA:TRUE', '-addext', 'keyUsage=critical,keyCertSign,cRLSign')
    openssl('req', '-new', '-newkey', 'rsa:3072', '-nodes', '-keyout', 'server.key',
            '-out', 'server.csr', '-subj', '/CN=broker')
    (directory/'server.ext').write_text('subjectAltName='+','.join(
        ['DNS:'+n for n in names]+['IP:'+ip for ip in ips])+
        '\nbasicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\n')
    openssl('x509', '-req', '-in', 'server.csr', '-CA', 'ca.crt', '-CAkey', 'ca.key',
            '-CAcreateserial', '-out', 'server.crt', '-days', '30', '-extfile', 'server.ext')
    openssl('req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', 'untrusted.key',
            '-out', 'untrusted.crt', '-days', '30', '-subj', '/CN=Untrusted test CA')
    for i, role in enumerate(ROLES + ['device_'+name for name in args.extra_device]):
        password = secrets.token_hex(24)
        (directory/(role+'.password')).write_text(password+'\n')
        command = ['docker','run','--rm','-i','--user',f'{os.getuid()}:{os.getgid()}',
                   '--mount',f'type=bind,source={directory},target=/work',
                   '--entrypoint','mosquitto_passwd',BROKER_IMAGE]
        if i == 0:
            command.append('-c')
        command += ['/work/passwords', role]
        run(command, input=(password+'\n'+password+'\n').encode())
    registry = {name: {'topic': 'iot/sensors/'+name, 'key_epoch': 1,
                       'database_device_id': index,
                       'key_hex': secrets.token_hex(16)}
                for index,name in enumerate(['raspb1','smoke'] + args.extra_device, 1)}
    (directory/'registry.json').write_text(json.dumps(registry))
    for file in directory.iterdir():
        file.chmod(0o600)
    print('Local security material created (0700/0600); values withheld')


if __name__ == '__main__':
    main()

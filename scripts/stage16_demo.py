"""Single local Stage16 entrypoint; reuse Stage9 control, never reset authority."""
import argparse
import hashlib
import importlib.util
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import subprocess
import sys
import time

from scripts.stage9_common import Demo as Stage9Demo

PROJECT = r'lcm-stage16-final-demo-[a-z0-9-]{1,18}'
SERVICES = ['postgres', 'mongo', 'broker', 'receiver', 'outbox-relay', 'web', 'policy-worker']
AGENTS = ['device-alpha', 'device-beta', 'device-gamma']
AUXILIARY = {('mongo', '/data/configdb'), ('broker', '/mosquitto/log')}


def write(path, value):
    """Atomic private metadata, not a key/nonce authority."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, indent=2) + '\n')
    temp.chmod(0o600)
    temp.replace(path)


def docker(*args):
    return subprocess.check_output(['docker', *args], text=True, timeout=30)


def material(root):
    names = ['compose.env', 'control.json', 'mqtt/registry.json', 'mqtt/ca.crt', 'stage16.json', 'network.json']
    names += [str(p.relative_to(root)) for folder in ['mqtt', 'mongo', 'accounts', 'alpha', 'beta', 'gamma']
              for p in (root/folder).rglob('*') if p.is_file() and not p.name.endswith('.lock')]
    return {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in sorted(set(names))}


def preflight(directory, project, subnet, web_port, mqtt_port):
    if not re.fullmatch(PROJECT, project):
        raise ValueError('Dedicated lcm-stage16-final-demo-* project required')
    if sys.version_info < (3, 12):
        raise ValueError('Python 3.12+ required; tested host Python is recorded separately')
    missing = [m for m in ['requests', 'sqlalchemy', 'paho', 'cryptography', 'flask'] if importlib.util.find_spec(m) is None]
    if missing:
        raise ValueError('Install pinned host dependencies: ' + ', '.join(missing))
    if not shutil.which('openssl'):
        raise ValueError('OpenSSL CLI required for fresh TLS provisioning')
    docker('info', '--format', '{{.ServerVersion}}')
    compose = subprocess.check_output(['docker', 'compose', 'version', '--short'], text=True).strip()
    network = ipaddress.ip_network(subnet, strict=True)
    if network.version != 4 or network.prefixlen != 24 or not network.is_private:
        raise ValueError('Explicit private IPv4 /24 subnet required')
    ids = docker('network', 'ls', '-q').split()
    for row in json.loads(docker('network', 'inspect', *ids)) if ids else []:
        owner = (row.get('Labels') or {}).get('com.docker.compose.project')
        for item in row['IPAM'].get('Config') or []:
            existing = item.get('Subnet')
            if existing and ipaddress.ip_network(existing).version == 4 and network.overlaps(ipaddress.ip_network(existing)) and owner != project:
                raise ValueError('Requested subnet overlaps an existing network; choose another /24, never delete old networks')
    root = Path(directory).resolve()
    used = root.exists()
    volumes = docker('volume', 'ls', '-q', '--filter', 'label=com.docker.compose.project='+project).split()
    containers = docker('ps', '-aq', '--filter', 'label=com.docker.compose.project='+project).split()
    if not used and (volumes or containers):
        raise ValueError('Project name already used; choose a new name')
    running = bool(docker('ps', '-q', '--filter', 'label=com.docker.compose.project='+project).strip())
    if not running:
        for port in [web_port, mqtt_port]:
            if type(port) is not int or not 0 <= port <= 65535:
                raise ValueError('Port must be 0..65535; 0 allocates a new loopback host port')
            if port:
                with socket.socket() as check:
                    check.bind(('127.0.0.1', port))
    parent = root if used else next(p for p in [root.parent, *root.parents] if p.exists())
    available = int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:'))) * 1024
    free = shutil.disk_usage(parent).free
    if available < 1024**3 or free < 2*1024**3:
        raise ValueError('At least 1 GiB available RAM and 2 GiB free disk required')
    images = {}
    for image in [project+'-runtime', project+'-tests']:
        result = subprocess.run(['docker', 'image', 'inspect', image, '--format', '{{.Id}}'], capture_output=True, text=True)
        images[image] = result.stdout.strip() if result.returncode == 0 else 'MISSING: first start requires --build'
    if used:
        d = Demo(root)
        d.check_material()
        d.check_volumes()
    return dict(status='PASS', project=project, compose=compose, python=sys.version.split()[0], subnet=str(network),
                available_memory_bytes=available, free_disk_bytes=free, existing_state=used, images=images,
                shadow='OPTIONAL_RESEARCH_DEMO_UNAVAILABLE: main demo has no model dependency; use documented isolated Stage15 demo',
                exit_code=0)


def prepare(directory, project, subnet, web_port, mqtt_port):
    preflight(directory, project, subnet, web_port, mqtt_port)
    root = Path(directory).resolve()
    if root.exists():
        raise ValueError('Directory exists; prepare never overwrites state. Use resume')
    from scripts.prepare_control import prepare as provision
    provision(root, project)
    registry = json.loads((root/'mqtt/registry.json').read_text())
    (root/'mqtt/registry.json').write_text(json.dumps({k: v for k, v in registry.items() if k in ['alpha', 'beta', 'gamma']}))
    accounts = root/'accounts'
    accounts.mkdir(mode=0o700)
    for role in ['admin', 'operator', 'viewer']:
        file = accounts/(role+'.password')
        file.write_text(secrets.token_urlsafe(30)+'\n')
        file.chmod(0o600)
    env = root/'compose.env'
    text = env.read_text()
    for name, value in [('WEB_BIND_PORT', web_port), ('MQTT_BIND_PORT', mqtt_port)]:
        text = re.sub(r'^'+name+r'=.*$', name+'='+str(value), text, flags=re.MULTILINE)
    env.write_text(text)
    write(root/'network.json', {'networks': {'default': {'ipam': {'config': [{'subnet': subnet}]}}}})
    write(root/'stage16.json', dict(schema=1, project=project, subnet=subnet, web_port=web_port, mqtt_port=mqtt_port,
                                  devices=['alpha', 'beta', 'gamma'], shadow='OPTIONAL_RESEARCH_DEMO_UNAVAILABLE',
                                  shadow_reason='Explicit separate Stage15 research stand; no private model dependency in main demo'))
    write(root/'material.json', material(root))
    print('Fresh private demo prepared; accounts demo-admin/demo-operator/demo-viewer. Passwords remain in accounts/*.password (0600).')


class Demo(Stage9Demo):
    def __init__(self, directory):
        super().__init__(directory)
        self.identity = json.loads((self.root/'stage16.json').read_text())

    def check_material(self):
        if (self.root/'agents-start-intent.json').exists() and not (self.root/'setup-committed.json').exists():
            raise ValueError('Used setup marker missing; no initial setup under old keys')
        if material(self.root) != json.loads((self.root/'material.json').read_text()):
            raise ValueError('Provisioned private material changed; reviewed recovery required, no reprovisioning')
        for folder in ['mqtt', 'mongo', 'accounts', 'alpha', 'beta', 'gamma']:
            for p in [self.root/folder, *(self.root/folder).rglob('*')]:
                if p.stat().st_mode & 0o077:
                    raise ValueError('Private material permissions must be 0700/0600')

    def check_volumes(self):
        marker = self.root/'used-volumes.json'
        if marker.exists():
            for name, expected in json.loads(marker.read_text()).items():
                auxiliary = expected.get('auxiliary', False)
                if auxiliary:
                    if (expected.get('service'), expected.get('target')) not in AUXILIARY or not re.fullmatch('[0-9a-f]{64}', name):
                        raise ValueError('Invalid auxiliary volume identity')
                    if self.auxiliary_bindings().get(name) != (expected['service'], expected['target']):
                        raise ValueError('Auxiliary volume binding lost/replaced')
                elif not name.startswith(self.project+'_'):
                    raise ValueError('Volume identity mismatch')
                try:
                    actual = json.loads(docker('volume', 'inspect', name))[0]
                except subprocess.CalledProcessError as exc:
                    raise ValueError('Used volume missing; refusing new state under old keys') from exc
                if actual.get('CreatedAt') != expected['created_at'] or (not auxiliary and (actual.get('Labels') or {}).get('com.docker.compose.project') != self.project):
                    raise ValueError('Used volume replaced/misbound; reviewed recovery/rekey required')
        elif (self.root/'agents-start-intent.json').exists():
            raise ValueError('Used volume marker missing; reviewed recovery required')

    def auxiliary_bindings(self):
        ids = docker('ps', '-aq', '--filter', 'label=com.docker.compose.project='+self.project).split()
        result = {}
        for row in json.loads(docker('inspect', *ids)) if ids else []:
            service = row['Config']['Labels'].get('com.docker.compose.service')
            for mount in row['Mounts']:
                if mount['Type'] == 'volume' and (service, mount['Destination']) in AUXILIARY:
                    result[mount['Name']] = (service, mount['Destination'])
        return result

    def record_auxiliary(self):
        # Existing image-declared volumes are adopted by verified container binding,
        # never recreated/copied/reset. Only non-authoritative config/log paths.
        marker = self.root/'used-volumes.json'
        records = json.loads(marker.read_text())
        changed = False
        for name, (service, target) in self.auxiliary_bindings().items():
            if name in records:
                continue
            if not re.fullmatch('[0-9a-f]{64}', name):
                raise ValueError('Unexpected auxiliary volume name')
            row = json.loads(docker('volume', 'inspect', name))[0]
            records[name] = dict(created_at=row.get('CreatedAt'), auxiliary=True, service=service, target=target)
            changed = True
        if changed:
            write(marker, records)
        self.check_volumes()

    def initialize_volumes(self):
        self.check_volumes()
        if (self.root/'used-volumes.json').exists():
            return
        config = json.loads(self.run('config', '--format', 'json').stdout)
        records = {}
        for key, value in config['volumes'].items():
            name = value['name']
            if not name.startswith(self.project+'_'):
                raise ValueError('External volume forbidden')
            if subprocess.run(['docker', 'volume', 'inspect', name], capture_output=True).returncode == 0:
                raise ValueError('Unrecorded existing volume; reviewed recovery required')
            subprocess.run(['docker', 'volume', 'create', '--label', 'com.docker.compose.project='+self.project,
                            '--label', 'com.docker.compose.volume='+key, name], check=True, stdout=subprocess.DEVNULL)
            row = json.loads(docker('volume', 'inspect', name))[0]
            records[name] = dict(created_at=row.get('CreatedAt'))
        write(self.root/'used-volumes.json', records)

    def sqlite_snapshot(self):
        """Read-only logical authority check; never open an absent SQLite for writing."""
        snapshots = {}
        code = """import sqlite3,json;from pathlib import Path
p=Path('/state/device.db');assert p.is_file() and Path('/state/installed').is_file(),'Missing used SQLite/installed state'
c=sqlite3.connect('file:/state/device.db?mode=ro',uri=True);c.row_factory=sqlite3.Row
assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
s=dict(c.execute('SELECT * FROM state WHERE id=1').fetchone());s.pop('prepared',None)
s['nonce_reserved_high']=c.execute('SELECT high FROM nonce_reservation WHERE id=1').fetchone()[0]
s['ledger_count']=c.execute('SELECT count(*) FROM commands').fetchone()[0]
s['authority_failures']=c.execute('SELECT count(*) FROM authority_failure').fetchone()[0]
assert not s['authority_failures'];print(json.dumps(s));c.close()"""
        for device in ['alpha', 'beta', 'gamma']:
            result = subprocess.run(['docker', 'run', '--rm', '--network', 'none', '--read-only', '--user', '0',
                                     '-v', self.project+'_'+device+'-control:/state:ro', '--entrypoint', 'python',
                                     self.project+'-runtime', '-c', code], capture_output=True, text=True, timeout=30)
            self.commands.append(dict(command=['docker', 'run', 'read-only-sqlite-probe', device], exit_code=result.returncode))
            if result.returncode:
                raise ValueError('Used SQLite state unavailable/corrupt for '+device+'; no reset allowed')
            snapshots[device] = json.loads(result.stdout)
            if snapshots[device]['device'] != device or snapshots[device]['epoch'] != 1:
                raise ValueError('SQLite identity mismatch')
        return snapshots

    def detailed(self):
        r = self.run('run', '--rm', '-T', '--no-deps', '--entrypoint', 'python', 'tests', '-m', 'scripts.stage16_probe')
        return json.loads(r.stdout[r.stdout.index('{'):])

    def start(self, build=False, resume=False):
        preflight(self.root, self.project, self.identity['subnet'], self.identity['web_port'], self.identity['mqtt_port'])
        self.check_material()
        if resume and not (self.root/'used-volumes.json').exists():
            raise ValueError('Resume requires used state; run start once for a new project')
        self.check_volumes()
        if (self.root/'used-volumes.json').exists():
            self.record_auxiliary()
        if (self.root/'agents-start-intent.json').exists():
            sql = self.sqlite_snapshot()
            checkpoint = self.root/'stop-checkpoint.json'
            if checkpoint.exists():
                old = json.loads(checkpoint.read_text())['sqlite']
                for device, state in sql.items():
                    assert state['nonce_reserved_high'] >= old[device]['nonce_reserved_high'] and state['seq'] >= old[device]['seq'] and state['ledger_count'] >= old[device]['ledger_count'], 'SQLite authority rollback'
        if build:
            self.run('build', 'receiver', 'tests', timeout=1200)
        self.initialize_volumes()
        self.run('up', '-d', '--wait', '--wait-timeout', '120', *SERVICES, timeout=300)
        self.record_auxiliary()
        self.run('run', '--rm', '--no-deps', 'control-init')
        if not (self.root/'setup-committed.json').exists():
            self.probe('setup')
            write(self.root/'setup-committed.json', {'committed': True})
        checkpoint = self.root/'stop-checkpoint.json'
        if checkpoint.exists():
            before = json.loads(checkpoint.read_text())['pg']
            now = self.detailed()
            assert now['transitions'] >= before['transitions'] and now['effective_receipts'] >= before['effective_receipts'], 'PG history rollback'
            assert {r['event_id'] for r in before['identities']} <= {r['event_id'] for r in now['identities']}, 'PG admission history rollback'
            assert {r['_id'] for r in before['mongo_identities']} <= {r['_id'] for r in now['mongo_identities']}, 'Mongo history rollback'
            old = {r['device_id']: r for r in before['devices']}
            for row in now['devices']:
                prior = old[row['device_id']]
                assert row['sequence_reserved'] >= prior['sequence_reserved'] and row['command_sequence'] >= prior['command_sequence'], 'PG authority rollback'
        prior_telemetry = self.probe('status')['telemetry']
        write(self.root/'agents-start-intent.json', {'manual_authorized_control': True})
        self.run('up', '-d', '--wait', '--wait-timeout', '90', 'control-worker', *AGENTS, timeout=180)
        deadline = time.monotonic()+50
        while time.monotonic()<deadline:
            result = self.detailed()
            if all(any(r['device_id']==device and r['sequence_number']>prior_telemetry.get(device,{}).get('max_sequence',0) for r in result['identities']) and any(r['device_id']==device and r['sequence_number']>prior_telemetry.get(device,{}).get('max_sequence',0) for r in result['mongo_identities']) for device in ['alpha','beta','gamma']):
                break
            time.sleep(.3)
        else:
            raise ValueError('No new authenticated PG/Mongo telemetry from all three devices; refusing ready status')
        write(self.root/'last-start.json', dict(url=self.url(), status=result, commands=self.commands))
        print(json.dumps(dict(url=self.url(), devices=result['devices'], policy='DRY_RUN', trusted_detector=False,
                              control='MANUAL_AUTHORIZED_CONTROL', shadow=self.identity['shadow'], secrets_printed=False), indent=2))

    def stop(self):
        try:
            running = docker('ps', '-q', '--filter', 'label=com.docker.compose.project='+self.project).strip()
            if running and (self.root/'agents-start-intent.json').exists():
                self.run('stop', *AGENTS)
                pg = self.detailed()
                write(self.root/'stop-checkpoint.json', dict(pg=pg, sqlite=self.sqlite_snapshot(), at=time.time()))
        finally:
            self.run('stop')
        print('Only this Stage16 project stopped; volumes, keys, SQLite and receipts retained.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['preflight', 'prepare', 'start', 'status', 'smoke', 'stop', 'resume', 'evidence'])
    parser.add_argument('--directory', type=Path, default=Path('.local-runtime/stage16/demo'))
    parser.add_argument('--project', default='lcm-stage16-final-demo-main')
    parser.add_argument('--subnet', default='10.216.16.0/24')
    parser.add_argument('--web-port', type=int, default=15016)
    parser.add_argument('--mqtt-port', type=int, default=18816)
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    try:
        if args.action == 'prepare':
            prepare(args.directory, args.project, args.subnet, args.web_port, args.mqtt_port)
            return
        if args.action == 'preflight':
            values = json.loads((args.directory/'stage16.json').read_text()) if (args.directory/'stage16.json').exists() else dict(project=args.project, subnet=args.subnet, web_port=args.web_port, mqtt_port=args.mqtt_port)
            print(json.dumps(preflight(args.directory, values['project'], values['subnet'], values['web_port'], values['mqtt_port']), indent=2))
            return
        d = Demo(args.directory)
        if args.action in ['start', 'resume']:
            d.start(args.build, resume=args.action == 'resume')
        elif args.action == 'stop':
            d.stop()
        elif args.action == 'status':
            print(json.dumps(d.detailed(), indent=2))
        else:
            if args.output is None or args.output.exists():
                raise ValueError('A new --output path is required; existing evidence is immutable')
            if args.action == 'smoke':
                from scripts.stage16_smoke import stage16_final_demo_smoke
                result = stage16_final_demo_smoke(d)
            else:
                result = dict(project=d.project, source_sha=docker_git_sha(), status=d.detailed(), commands=d.commands, exit_code=0)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, indent=2)+'\n')
            print('Evidence written; exit0 means authoritative assertions passed.')
    except (ValueError, AssertionError, RuntimeError, OSError, subprocess.SubprocessError) as exc:
        # Private subprocess failure details stay local. Never dump environment/config.
        print('Stage16 blocked: '+str(exc), file=sys.stderr)
        raise SystemExit(2)


def docker_git_sha():
    return subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()


if __name__ == '__main__':
    main()

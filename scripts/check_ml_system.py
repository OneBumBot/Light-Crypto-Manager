"""Isolated real-container ML availability, restart and Mongo outage exercise."""
import argparse
from pathlib import Path
import subprocess


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file',type=Path,required=True)
    parser.add_argument('--reuse-installed-model',action='store_true')
    args=parser.parse_args()
    values=dict(line.split('=',1) for line in args.env_file.read_text().splitlines() if '=' in line and not line.startswith('#'))
    if not values.get('COMPOSE_PROJECT_NAME','').startswith('lcm-stage6'):
        parser.error('Explicit isolated lcm-stage6 project required')
    base=['docker','compose','--env-file',str(args.env_file),'--profile','demo','--profile','web']
    def run(*parts):subprocess.run(base+list(parts),check=True)
    def probe(phase):run('run','--rm','--no-deps','--entrypoint','python','tests','-m','scripts.ml_system_probe',phase)
    run('up','-d','--wait','--wait-timeout','150','postgres','mongo','broker','receiver','outbox-relay','demo-setup','publisher','web')
    run('run','--rm','--no-deps','-e','DEVICE_REGISTRY_FILE=/run/lcm/registry.json','--entrypoint','python','tests','-m','scripts.provision_registry')
    run('up','-d','--no-deps','ml-worker')
    if not args.reuse_installed_model:probe('unavailable')
    else:print('INFO: reusing installed model; fresh-project missing-model check is in the initial report',flush=True)
    run('run','--rm','--no-deps','ml-model-init')
    probe('publish');probe('marked');probe('scored')
    run('restart','ml-worker');probe('verify')
    run('stop','ml-worker')
    probe('publish');probe('marked')
    try:
        run('stop','mongo')
        run('up','-d','--no-deps','ml-worker')
        probe('retry')
    finally:run('up','-d','--no-deps','--wait','mongo')
    probe('scored');probe('verify')
    print('PASS: optional ML, three devices, immutable reload, durable dedupe and Mongo recovery')

if __name__=='__main__':main()

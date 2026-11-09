"""Isolated Compose failure exercise. Existing application volumes are never used."""
import argparse
from pathlib import Path
import subprocess


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file',type=Path,required=True)
    args=parser.parse_args()
    values=dict(line.split('=',1) for line in args.env_file.read_text().splitlines() if '=' in line and not line.startswith('#'))
    if not values.get('COMPOSE_PROJECT_NAME','').startswith(('lcm-stage5','lcm-stage6')):
        parser.error('Failure exercise requires explicit lcm-stage5/lcm-stage6 isolated project')
    base=['docker','compose','--env-file',str(args.env_file),'--profile','demo','--profile','web','--profile','checks']
    def run(*parts,expected=0):
        result=subprocess.run(base+list(parts))
        if result.returncode!=expected:
            raise RuntimeError('Compose check failed: '+parts[0])
    def probe(phase,expected=0):
        run('run','--rm','--no-deps','--entrypoint','python','tests','-m','scripts.dual_database_probe',phase,expected=expected)
    run('up','-d','--wait','--wait-timeout','150','--scale','outbox-relay=2',
        'postgres','mongo','broker','receiver','outbox-relay','demo-setup','publisher','web')
    run('run','--rm','--no-deps','-e','DEVICE_REGISTRY_FILE=/run/lcm/registry.json','--entrypoint','python','tests','-m','scripts.provision_registry')
    probe('demo')
    probe('publish'); probe('delivered'); probe('identity')
    try:
        run('stop','mongo')
        probe('publish'); probe('pending')
    finally:
        run('up','-d','--no-deps','--wait','mongo')
    probe('delivered')
    try:
        run('stop','postgres')
        probe('publish')
    finally:
        run('up','-d','--no-deps','--wait','postgres')
    probe('delivered')
    run('up','-d','--no-deps','--force-recreate','--wait','receiver')
    run('restart','outbox-relay')
    probe('replay'); probe('verify')
    # Deterministic real process crash: stop other producers/relays temporarily.
    run('stop','publisher','outbox-relay')
    probe('publish')
    probe('crash',expected=19)
    run('up','-d','--no-deps','--wait','--scale','outbox-relay=2','outbox-relay')
    probe('delivered')
    run('up','-d','--no-deps','publisher')
    print('PASS: multi-device TLS ingestion, Mongo/PG outage recovery, process crash, two relays and restarts')

if __name__=='__main__': main()

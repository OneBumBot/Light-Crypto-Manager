"""Destructive-service failure tests restricted to isolated stage7 project, preserving volumes."""
import argparse
from pathlib import Path
import subprocess


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--env-file',type=Path,required=True);args=p.parse_args()
    values=dict(line.split('=',1) for line in args.env_file.read_text().splitlines() if '=' in line and not line.startswith('#'))
    if not values.get('COMPOSE_PROJECT_NAME','').startswith('lcm-stage7'):p.error('Explicit lcm-stage7 isolated project required')
    base=['docker','compose','--env-file',str(args.env_file),'--profile','demo','--profile','web','--profile','policy']
    def run(*parts):subprocess.run(base+list(parts),check=True)
    def probe(phase):run('run','--rm','--no-deps','--entrypoint','python','tests','-m','scripts.policy_system_probe',phase)
    def telemetry(phase):run('run','--rm','--no-deps','--entrypoint','python','tests','-m','scripts.dual_database_probe',phase)
    run('up','-d','--wait','--wait-timeout','150','--scale','policy-worker=2','postgres','mongo','broker','receiver','outbox-relay','publisher','web','policy-worker')
    run('run','--rm','--no-deps','-e','DEVICE_REGISTRY_FILE=/run/lcm/registry.json','--entrypoint','python','tests','-m','scripts.provision_registry')
    telemetry('publish');telemetry('delivered');probe('replay');probe('snapshot')
    run('stop','policy-worker');telemetry('publish');telemetry('delivered');probe('queued')
    run('up','-d','--no-deps','--scale','policy-worker=2','policy-worker');probe('verify')
    run('restart','policy-worker');probe('verify')
    try:
        run('stop','postgres');probe('unavailable')
    finally:run('up','-d','--no-deps','--wait','postgres')
    probe('verify')
    print('PASS: policy-only downtime, two workers, replay attribution, restart and real PostgreSQL outage recovery')

if __name__=='__main__':main()

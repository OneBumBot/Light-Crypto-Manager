"""Create private local Compose configuration, without overwriting existing files."""

import argparse
import os
from pathlib import Path
import re
import secrets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path, default=Path('.env.compose'))
    parser.add_argument('--project', default='lightcrypto')
    parser.add_argument('--mqtt-port', type=int, default=8883)
    parser.add_argument('--web-port', type=int, default=5000)
    args = parser.parse_args()
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,45}', args.project):
        parser.error('project must be a short lowercase Compose project name')
    if not all(0 <= port <= 65535 for port in [args.mqtt_port, args.web_port]):
        parser.error('ports must be between 0 and 65535 (0 means a random host port)')
    template = Path(__file__).resolve().parents[1] / 'deploy/compose.env.example'
    content = template.read_text()
    values = {
        'COMPOSE_PROJECT_NAME': args.project,
        'POSTGRES_PASSWORD': secrets.token_hex(24),
        'FLASK_SECRET_KEY': secrets.token_hex(32),
        'MQTT_BIND_PORT': str(args.mqtt_port),
        'WEB_BIND_PORT': str(args.web_port),
    }
    for name, value in values.items():
        content = re.sub(rf'^{name}=.*$', f'{name}={value}', content, flags=re.MULTILINE)
    try:
        fd = os.open(args.env_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        parser.error('configuration already exists; no file was changed')
    with os.fdopen(fd, 'w') as stream:
        stream.write(content)
    print('Private Compose configuration created; secrets withheld')


if __name__ == '__main__':
    main()

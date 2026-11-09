"""Generate private MongoDB credentials; never overwrite existing material."""
import argparse
import os
from pathlib import Path
import secrets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    args.directory.mkdir(parents=True, mode=0o700, exist_ok=False)
    for role in ['root', 'relay', 'history']:
        (args.directory / (role + '.password')).write_text(secrets.token_hex(32) + '\n')
    print('Private MongoDB credentials generated (0700/0600); values withheld')


if __name__ == '__main__':
    main()

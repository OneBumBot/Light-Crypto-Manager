"""Local known-secret/history and permissions audit, printing paths/counts only."""
import argparse
import ast
import json
from pathlib import Path
import stat
import subprocess
import tarfile


def git(*args):
    return subprocess.check_output(['git',*args])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--secrets-dir',type=Path,required=True)
    args=parser.parse_args()
    secret_values=set()
    for root in [args.secrets_dir]:
        assert stat.S_IMODE(root.stat().st_mode)==0o700
        for path in root.iterdir():
            if not path.is_file(): continue
            assert stat.S_IMODE(path.stat().st_mode)==0o600, str(path)
            if path.suffix=='.password': secret_values.add(path.read_bytes().strip())
            elif path.name=='registry.json':
                secret_values.update(v['key_hex'].encode() for v in json.loads(path.read_text()).values())
            elif path.suffix=='.key': secret_values.add(path.read_bytes().strip())
    for path in Path('.local-runtime').glob('*.env'):
        assert stat.S_IMODE(path.stat().st_mode)==0o600
        for line in path.read_text().splitlines():
            if '=' not in line: continue
            name,value=line.split('=',1)
            if value and any(word in name for word in ['PASSWORD','SECRET','KEY_HEX']): secret_values.add(value.encode())
    backup=Path('.local-baseline/original-src.tar.gz')
    if backup.exists():
        with tarfile.open(backup) as archive:
            for name in ['src/web/config.py','src/web/app.py','src/publisher/mqtt_pub.py','src/brocker/mqtt_brocker.py']:
                for node in ast.walk(ast.parse(archive.extractfile(name).read().decode())):
                    if isinstance(node,ast.Assign):
                        names=[x.id for x in node.targets if isinstance(x,ast.Name)]
                        if any(x in ['ASCON_KEY','DB_PASSWORD','SQLALCHEMY_DATABASE_URI'] for x in names) and isinstance(node.value,ast.Constant):
                            v=node.value.value;secret_values.add(v if isinstance(v,bytes) else v.encode())
                        if 'SECRET_KEY' in names and isinstance(node.value,ast.BoolOp): secret_values.add(node.value.values[-1].value.encode())
                    if isinstance(node,ast.Dict):
                        for key,value in zip(node.keys,node.values):
                            if isinstance(key,ast.Constant) and key.value=='password' and isinstance(value,ast.Constant): secret_values.add(value.value.encode())
    checked=set()
    for commit in git('rev-list','--all').decode().splitlines():
        for entry in git('ls-tree','-rz',commit).split(b'\0'):
            if not entry: continue
            info,name=entry.split(b'\t',1);mode,kind,oid=info.split()
            assert mode!=b'160000',name.decode()
            if oid not in checked:
                data=git('cat-file','blob',oid.decode())
                assert not any(value in data for value in secret_values),name.decode()
                checked.add(oid)
    paths=git('ls-files','--cached','--others','--exclude-standard').decode().splitlines()
    for name in paths:
        path=Path(name)
        if path.is_file(): assert not any(value in path.read_bytes() for value in secret_values),name
    print(f'PASS: known legacy/current secret scan ({len(checked)} Git blobs and working-tree candidates)')
    print('PASS: private input directories 0700 and generated files/env 0600')


if __name__=='__main__': main()

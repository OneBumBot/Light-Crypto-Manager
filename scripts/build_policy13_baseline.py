"""Rebuild the original policy controller without checkout/main changes or private input."""
import argparse,io,tarfile,tempfile,subprocess,hashlib,json,shutil,re
from pathlib import Path
BASELINE='649a80ff7f7d66f72f5f483b384754ae594f221e'


def main():
    p=argparse.ArgumentParser();p.add_argument('--image-prefix',default='lcm-stage13-policy-baseline-reference');a=p.parse_args()
    if not re.fullmatch(r'lcm-stage13-policy-[a-z0-9-]{1,40}',a.image_prefix):p.error('Stage13 image namespace required')
    with tempfile.TemporaryDirectory(prefix='lcm-policy13-baseline-') as directory:
        root=Path(directory);archive=subprocess.check_output(['git','archive','--format=tar',BASELINE])
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:tar.extractall(root,filter='data')
        shutil.copyfile('scripts/install_stage13.py',root/'scripts/install_stage13.py')
        docker=root/'Dockerfile';s=docker.read_text();needle='COPY alembic.ini /app/alembic.ini';assert needle in s
        docker.write_text(s.replace(needle,'COPY scripts/install_stage13.py /app/scripts/\n'+needle))
        for path in ['src/policy/worker.py','src/policy/state.py','src/policy/engine.py']:
            assert (root/path).read_bytes()==subprocess.check_output(['git','show',BASELINE+':'+path])
        for target in ['runtime','tests']:subprocess.run(['docker','build','--target',target,'-t',a.image_prefix+'-'+target,str(root)],check=True,timeout=600)
        print(json.dumps(dict(baseline_sha=BASELINE,stage13_installer_overlay_only=True,core_hashes={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in ['src/policy/worker.py','src/policy/state.py','src/policy/engine.py']},exit_code=0)))
if __name__=='__main__':main()

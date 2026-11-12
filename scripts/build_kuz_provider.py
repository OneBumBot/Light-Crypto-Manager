"""Offline reproducible build of pinned local Go source, never reads runtime keys."""
import os,subprocess,argparse,json,hashlib
from pathlib import Path


def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=Path('.local-runtime/stage11/bin/lcm-kuz-mgm'));a=p.parse_args()
 root=Path(__file__).resolve().parents[1];a.output=a.output.resolve();a.output.parent.mkdir(parents=True,exist_ok=True)
 manifest=json.loads((root/'third_party/go-gostcrypto/PROVENANCE.json').read_text())
 for name,expected in manifest['files'].items():
  if hashlib.sha256((root/'third_party/go-gostcrypto'/name).read_bytes()).hexdigest()!=expected:raise ValueError('Provider source hash mismatch')
 env=dict(os.environ,CGO_ENABLED='0',GOTOOLCHAIN='local',GOPROXY='off',GOSUMDB='off',GOCACHE=str(root/'.local-runtime/stage11/gocache'))
 subprocess.run(['go','build','-trimpath','-buildvcs=false','-ldflags=-buildid=','-o',str(a.output),'.'],cwd=root/'native/kuzprovider',env=env,check=True,timeout=120)
 print(json.dumps(dict(provider_revision=manifest['revision'],binary_sha256=hashlib.sha256(a.output.read_bytes()).hexdigest(),go=subprocess.check_output(['go','version'],text=True).strip(),cgo=False,exit_code=0)))

if __name__=='__main__':main()

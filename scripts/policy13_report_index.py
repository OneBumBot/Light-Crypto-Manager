"""Index actual Stage13 artifacts without rewriting their measurement provenance."""
import json,hashlib,subprocess,argparse,gzip
from pathlib import Path
from datetime import datetime,timezone


def main():
 p=argparse.ArgumentParser();p.add_argument('--reports',type=Path,default=Path('docs/reports/stage13'));a=p.parse_args();root=a.reports
 sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();baseline='649a80ff7f7d66f72f5f483b384754ae594f221e'
 source={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for d in ['src/policy','scripts'] for f in Path(d).glob('*.py') if d=='src/policy' or 'policy13' in f.name}
 files=[]
 for f in sorted(root.rglob('*')):
  if f.is_file() and f.name not in ['artifact-index.json','index-build.txt']:files.append(dict(path=str(f.relative_to(root)),bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest()))
 changes=subprocess.check_output(['git','diff','--name-only',baseline],text=True).splitlines()
 report=dict(baseline_sha=baseline,index_source_sha=sha,created_at=datetime.now(timezone.utc).isoformat(),source_hashes=source,changed_tracked_files=changes,files=files,provenance_limit='Raw measured image/code hashes take precedence over later index HEAD; historical logs retained with failures and excluded repeats. Index excludes itself and its diagnostic stdout index-build.txt.',exit_code=0)
 (root/'artifact-index.json').write_text(json.dumps(report,indent=2));print('Indexed',len(files),'actual artifacts; exit0')
if __name__=='__main__':main()

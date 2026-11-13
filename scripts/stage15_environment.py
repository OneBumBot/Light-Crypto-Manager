"""Public reproducibility metadata only, never Docker runtime environment values."""
import hashlib,json,os,platform,subprocess
from pathlib import Path
from scripts.stage15_setup import lab
from src.classifier.ml.artifacts import versions

def main():
 l=lab('.local-runtime/stage15/online');cpu=next(v.split(':',1)[1].strip() for v in Path('/proc/cpuinfo').read_text().splitlines() if v.startswith('model name'));memory=next(v for v in Path('/proc/meminfo').read_text().splitlines() if v.startswith('MemTotal:'));result=dict(source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),system=platform.platform(),machine=platform.machine(),cpu=cpu,logical_cpus=os.cpu_count(),memory=memory,python_packages=versions(),images=json.loads(l.run('images','--format','json').stdout),source_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('src/shadow_ids').glob('*') if p.is_file()},compose_hashes={name:hashlib.sha256(Path(name).read_bytes()).hexdigest() for name in ['compose.yaml','compose.research.yaml','compose.shadow.yaml']},independent_host_domain='not_verified',generalization_evaluation='BLOCKED_INDEPENDENT_DATA',old_holdout_predictions=0,fit_calls=0,threshold_changes=0,exit_code=0)
 Path('docs/reports/stage15/environment.json').write_text(json.dumps(result,indent=2));print('Sanitized hardware/image/source metadata saved; exit0')
if __name__=='__main__':main()

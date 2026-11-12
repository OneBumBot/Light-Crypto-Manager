"""Lossless raw artifact compression with SHA256 manifest; keep local working copies."""
import argparse,gzip,hashlib,json
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('--reports',type=Path,required=True);a=p.parse_args();manifest=[]
    for path in sorted(a.reports.rglob('*')):
        if not path.is_file() or path.name not in ['agent-events.json','committed.json','timings.csv','crypto-microbenchmark.csv']:continue
        target=Path(str(path)+'.gz');data=path.read_bytes()
        if target.exists():
            if gzip.decompress(target.read_bytes())!=data:raise ValueError('Immutable compressed artifact mismatch')
        else:target.write_bytes(gzip.compress(data,compresslevel=9,mtime=0))
        manifest.append(dict(path=str(target.relative_to(a.reports)),uncompressed_sha256=hashlib.sha256(data).hexdigest(),uncompressed_bytes=len(data),compressed_bytes=target.stat().st_size))
    output=a.reports/'raw-artifacts.json'
    if output.exists():raise ValueError('Immutable compression manifest exists')
    output.write_text(json.dumps(manifest,indent=2));print('Losslessly archived',len(manifest),'artifacts; local working copies retained')

if __name__=='__main__':main()

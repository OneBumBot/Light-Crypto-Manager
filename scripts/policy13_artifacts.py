"""Lossless archival of new Stage13 raw JSON only; historical reports are never touched."""
import argparse,gzip,hashlib,json
from pathlib import Path


def read_json(path):
 path=Path(path)
 if path.exists():return json.loads(path.read_text())
 return json.loads(gzip.decompress(path.with_suffix(path.suffix+'.gz').read_bytes()))


def main():
 p=argparse.ArgumentParser();p.add_argument('--reports',type=Path,default=Path('docs/reports/stage13'));a=p.parse_args()
 if a.reports.resolve()!=Path('docs/reports/stage13').resolve():p.error('Only new Stage13 reports')
 records=[]
 for name in ['agents.json','sources.json','ledger-final.json']:
  for path in a.reports.glob('*/'+name):
   data=path.read_bytes();target=path.with_suffix('.json.gz')
   compressed=gzip.compress(data,mtime=0);assert gzip.decompress(compressed)==data
   if target.exists():assert gzip.decompress(target.read_bytes())==data
   else:target.write_bytes(compressed)
   records.append(dict(path=str(path),archive=str(target),sha256=hashlib.sha256(data).hexdigest(),raw_bytes=len(data),archive_bytes=target.stat().st_size));path.unlink()
 old=a.reports/'raw-archive.json'
 previous=json.loads(old.read_text())['files'] if old.exists() else []
 old.write_text(json.dumps(dict(files=previous+records,lossless=True,scope='New Stage13 raw JSON only',exit_code=0),indent=2))
 print('Lossless archival',len(records),'Stage13 JSON files; exit0')
if __name__=='__main__':main()

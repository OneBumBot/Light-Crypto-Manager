"""Bounded unauthenticated official MQTTset downloads; no credentials or access bypass."""
import argparse
from datetime import datetime,timezone
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import urllib.parse
import urllib.request
import zipfile

FILES={'Data/CSV/bruteforce.csv':5*1024*1024,'Data/FINAL_CSV/mqttdataset_reduced.csv':60*1024*1024,
       'Data/README.md':10000,'code/parser/rawparsing_normal.py':20000,'code/processingdata_ml.py':20000}


def get(url,limit):
    with urllib.request.urlopen(url,timeout=30) as response:
        if response.status!=200 or 'html' in response.headers.get('Content-Type',''):raise ValueError('Public source unavailable; supply local file, do not bypass login')
        result=response.read(limit+1)
        if len(result)>limit:raise ValueError('Download exceeds explicit resource cap')
        return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',type=Path,required=True);p.add_argument('--file',choices=FILES,required=True)
    args=p.parse_args();os.umask(0o077);root=args.directory;root.mkdir(parents=True,exist_ok=True,mode=0o700)
    if root.is_symlink() or root.stat().st_mode&0o077:raise ValueError('Private output directory required')
    metadata_url='https://www.kaggle.com/api/v1/datasets/view/cnrieiit/mqttset'
    meta=json.loads(get(metadata_url,1024*1024))
    if meta['licenseName']!='CC BY-NC-SA 4.0' or meta['currentVersionNumber']!=5:raise ValueError('Dataset version/license changed; explicit review required')
    limit=FILES[args.file]
    if shutil.disk_usage(root).free<limit*3:raise ValueError('Insufficient free disk')
    path=root/Path(args.file).name
    if path.exists():raise FileExistsError('Refusing to overwrite a downloaded source')
    url='https://www.kaggle.com/api/v1/datasets/download/cnrieiit/mqttset/'+urllib.parse.quote(args.file,safe='')+'?datasetVersionNumber=5'
    payload=get(url,limit)
    if payload[:2]==b'PK':
        with zipfile.ZipFile(io.BytesIO(payload)) as z:
            if len(z.infolist())!=1 or z.infolist()[0].file_size>limit:raise ValueError('Unexpected archive size/members')
            payload=z.read(z.namelist()[0])
    if len(payload)>limit:raise ValueError('Expanded source exceeds cap')
    with path.open('xb') as stream:stream.write(payload)
    result=dict(source_url='https://www.kaggle.com/datasets/cnrieiit/mqttset',metadata_url=metadata_url,
        dataset_version=5,license='CC BY-NC-SA 4.0',file=args.file,bytes=len(payload),sha256=hashlib.sha256(payload).hexdigest(),
        downloaded_at=datetime.now(timezone.utc).isoformat(),distribution='private noncommercial research; no automatic data/weights publication')
    path.with_suffix(path.suffix+'.source.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))

if __name__=='__main__':main()

"""Aggregate bounded public CSV audits. Never prints payload, usernames or passwords."""
import argparse
import json
from pathlib import Path
import sys
import pandas as pd
from src.classifier.ml.artifacts import file_hash,versions
from src.classifier.research.schema import FEATURES


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();results=[]
    for name in ['bruteforce.csv','mqttdataset_reduced.csv']:
        path=args.directory/name
        if path.stat().st_size>80*1024*1024:raise ValueError('Audit exceeds fixed80MiB input bound')
        f=pd.read_csv(path,dtype=str,keep_default_na=False,nrows=400001)
        if len(f)>400000:raise ValueError('Explicit audit row bound exceeded; no silent sampling')
        value=dict(file=name,bytes=path.stat().st_size,sha256=file_hash(path),rows=len(f),columns=list(f),
            exact_reduced_row_duplicates=int(f.duplicated().sum()),missing_counts={k:int((f[k]=='').sum()) for k in f},
            required_passive_features_missing=sorted(set(FEATURES)-set(f)))
        if 'target' in f:
            value['classes']={k:int(v) for k,v in f.target.value_counts().items()}
            value['duplicates_by_class']={k:int(g.duplicated().sum()) for k,g in f.groupby('target')}
            value['capture_provenance_available']=False
        else:
            value.update(tcp_sessions=int(f['tcp.stream'].nunique()),captures=1,packet_label_scope='capture_scenario from author parser, not per-frame audit',
                distinct_source_ips=int(f['ip.src'].nunique()),distinct_destination_ips=int(f['ip.dst'].nunique()),
                epoch_range=[float(pd.to_numeric(f['frame.time_epoch']).min()),float(pd.to_numeric(f['frame.time_epoch']).max())])
        results.append(value)
    report=dict(schema_version=1,command=[sys.executable,'-m','scripts.audit_mqttset75',*sys.argv[1:]],versions=versions(),
        dataset_version=5,license='CC BY-NC-SA 4.0 (official Kaggle metadata)',source='https://www.kaggle.com/datasets/cnrieiit/mqttset',
        observations=results,new_models_trained=0,scientific_benchmark_performed=False,
        limitation='Equal reduced feature rows need not be copied physical packets; provenance was discarded, so independence cannot be reconstructed')
    with args.output.open('x') as stream:json.dump(report,stream,indent=2,allow_nan=False)
    print('Aggregate source audit saved; no raw payload/credentials emitted')

if __name__=='__main__':main()

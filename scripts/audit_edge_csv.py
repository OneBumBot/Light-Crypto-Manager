"""Streaming source audit: schema/types/counts only, never publishes raw packet rows."""
import argparse
from collections import Counter,defaultdict
import json
from pathlib import Path
import pandas as pd
from src.classifier.ml.artifacts import file_hash
from src.classifier.ml.schema import NETWORK_FEATURES,NETWORK_EXCLUDED_PROXIES


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if not args.data.is_file():parser.error('Source CSV missing')
    columns=list(pd.read_csv(args.data,nrows=0).columns)
    dtype_sets=defaultdict(set);missing=Counter();labels=Counter();types=Counter();count=0;contradictions=0;clock_only=0
    for frame in pd.read_csv(args.data,chunksize=50000,dtype=str,engine='python'):
        count+=len(frame)
        for name in columns:
            dtype_sets[name].add(str(frame[name].dtype));missing[name]+=int(frame[name].isna().sum())
        binary=pd.to_numeric(frame.Attack_label,errors='raise')
        contradictions+=int((~binary.isin([0,1]) | ((binary==0)!=(frame.Attack_type=='Normal'))).sum())
        labels.update(map(str,binary));types.update(frame.Attack_type.astype(str))
        clock_only+=int(frame['frame.time'].astype(str).str.fullmatch(r'\s*\d{4}\s+\d{2}:\d{2}:\d{2}\.\d+\s*').sum())
    proxies={name:{'normal':Counter(),'attack':Counter()} for name in NETWORK_EXCLUDED_PROXIES}
    for frame in pd.read_csv(args.data,usecols=NETWORK_EXCLUDED_PROXIES+['Attack_label'],dtype=str,chunksize=50000,engine='python'):
        for name in NETWORK_EXCLUDED_PROXIES:
            for token in ['0','0.0']:
                for label,key in [('0','normal'),('1','attack')]:
                    proxies[name][key][token]+=int(((frame[name]==token)&(frame.Attack_label==label)).sum())
    report=dict(source_name=args.data.name,source_sha256=file_hash(args.data),bytes=args.data.stat().st_size,
        parser_policy='Python CSV engine; raw strings; predictive types validated by explicit feature schema',
        rows=count,columns=columns,observed_chunk_dtypes={k:sorted(v) for k,v in dtype_sets.items()},missing_counts=dict(missing),
        verified_device_count=None,calendar_time_range=None,calendar_time_range_reason='year/time-only or unvalidated timestamp tokens',
        clock_only_timestamps=clock_only,binary_distribution=dict(labels),attack_type_distribution=dict(types),
        contradictory_targets=contradictions,core_features=NETWORK_FEATURES,excluded_proxy_zero_tokens=proxies,
        license_status='Not verified for this local copy; raw data and weights remain private',synthetic=False)
    with args.output.open('x') as stream:json.dump(report,stream,indent=2,allow_nan=False)
    print('Source audit complete:',count,'rows;',len(columns),'columns; target contradictions:',contradictions)

if __name__=='__main__':main()

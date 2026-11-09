"""Two-pass bounded real-data research sample, grouped by bidirectional endpoint pair."""
import argparse
from collections import Counter
import hashlib
import heapq
import json
import os
from pathlib import Path
import pandas as pd
from src.classifier.ml.schema import NETWORK_FEATURES
from src.classifier.ml.artifacts import file_hash


def group_ids(frame,seed):
    src=frame['ip.src_host'].fillna('__MISSING__').str.strip()
    dst=frame['ip.dst_host'].fillna('__MISSING__').str.strip()
    low=src.where(src<=dst,dst);high=dst.where(src<=dst,src)
    pairs=low+'|'+high
    mapping={pair:hashlib.sha256((str(seed)+'|'+pair).encode()).hexdigest() for pair in pairs.unique()}
    return pairs.map(mapping)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--max-rows',type=int,default=150000);parser.add_argument('--seed',type=int,default=42)
    parser.add_argument('--rare-group-fraction',type=float,default=0.02)
    parser.add_argument('--common-count',type=int,default=100)
    args=parser.parse_args()
    if not args.data.is_file():parser.error('Explicit dataset path does not exist')
    if args.max_rows<1000:parser.error('Sample bound too small')
    if args.output.exists():parser.error('Refusing to overwrite prepared data')
    os.umask(0o077);args.output.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    counts=Counter();distribution=Counter();clock_only=0;total=0
    for frame in pd.read_csv(args.data,usecols=['ip.src_host','ip.dst_host','frame.time','Attack_label','Attack_type'],dtype=str,chunksize=100000):
        binary=pd.to_numeric(frame.Attack_label,errors='raise')
        if not binary.isin([0,1]).all() or ((binary==0)!=(frame.Attack_type=='Normal')).any():
            raise ValueError('Contradictory source labels')
        total+=len(frame);distribution.update(frame.Attack_type);counts.update(group_ids(frame,args.seed))
        clock_only+=int(frame['frame.time'].fillna('').str.fullmatch(r'\s*\d{4}\s+\d{2}:\d{2}:\d{2}\.\d+\s*').sum())
    if not 0<args.rare_group_fraction<=1 or args.common_count<1:raise ValueError('Invalid cohort policy')
    selected_group_ids={group for group,count in counts.items() if count>=args.common_count or int(group[:8],16)/2**32<args.rare_group_fraction}
    if len(selected_group_ids)>args.max_rows:raise ValueError('More selected groups than sample budget')
    cap=max(k for k in range(1,1001) if sum(min(counts[g],k) for g in selected_group_ids)<=args.max_rows)
    heaps={};offset=0
    columns=NETWORK_FEATURES+['Attack_label','Attack_type','ip.src_host','ip.dst_host']
    for frame in pd.read_csv(args.data,usecols=columns,dtype=str,chunksize=100000):
        ids=group_ids(frame,args.seed)
        for index,record in enumerate(frame[NETWORK_FEATURES+['Attack_label','Attack_type']].to_dict('records')):
            source_index=offset+index;group=ids.iloc[index]
            if group not in selected_group_ids:continue
            priority=int.from_bytes(hashlib.blake2b(f'{args.seed}:{source_index}'.encode(),digest_size=8).digest(),'big')
            item=(-priority,source_index,record)
            heap=heaps.setdefault(group,[])
            if len(heap)<cap:heapq.heappush(heap,item)
            elif item[0]>heap[0][0]:heapq.heapreplace(heap,item)
        offset+=len(frame)
    records=[]
    for group,heap in heaps.items():
        for _,index,record in heap:records.append(dict(record,flow_group=group,source_index=index))
    records.sort(key=lambda row:row['source_index'])
    sample=pd.DataFrame(records);sample.to_csv(args.output,index=False)
    manifest=dict(source_file=args.data.name,source_sha256=file_hash(args.data),prepared_sha256=file_hash(args.output),
        source_rows=total,selected_rows=len(sample),source_groups=len(counts),selected_groups=sample.flow_group.nunique(),
        source_classes=dict(distribution),selected_classes={k:int(v) for k,v in sample.Attack_type.value_counts().items()},
        clock_only_timestamps=clock_only,rare_group_fraction=args.rare_group_fraction,common_count=args.common_count,per_group_cap=cap,max_rows=args.max_rows,random_state=args.seed,synthetic=False,
        grouping='bidirectional source/destination host-pair proxy; never a verified device/session identity',
        sampling='retain common host-pairs, hash-sample rare pairs; lowest seeded row hashes per retained group, no target-based selection' ,
        limitations=['clock-only timestamps cannot establish calendar chronology','host-pair split is not independent-device generalization','capped per-group sampling changes class prevalence','license not verified; do not distribute data or model'])
    args.output.with_suffix('.manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest,indent=2))

if __name__=='__main__':main()

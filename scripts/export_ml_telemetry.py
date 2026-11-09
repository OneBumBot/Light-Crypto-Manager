"""Explicit bounded export of verified MongoDB history for DEMO/RESEARCH training."""
import argparse
import csv
import json
import os
from pathlib import Path
from src.mongo_repository import MongoRepository,utc_millis
from src.telemetry import DEVICE
from src.classifier.ml.telemetry_features import RAW_FIELDS,raw_record
from src.classifier.ml.artifacts import file_hash


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device',action='append',required=True)
    parser.add_argument('--start',required=True);parser.add_argument('--end',required=True)
    parser.add_argument('--max-rows',type=int,default=10000);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if not 1<=args.max_rows<=300000 or any(not DEVICE.fullmatch(d) for d in args.device):parser.error('Invalid export bounds')
    start=utc_millis(args.start);end=utc_millis(args.end)
    if start>end:parser.error('Invalid date range')
    if args.output.exists():parser.error('Refusing to overwrite existing export')
    os.umask(0o077);args.output.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    repo=MongoRepository('history');count=0
    temporary=args.output.with_suffix(args.output.suffix+'.tmp')
    try:
        with temporary.open('x') as stream:
            writer=csv.DictWriter(stream,fieldnames=RAW_FIELDS);writer.writeheader()
            cursor=repo.collection.find({'device_id':{'$in':args.device},'received_at':{'$gte':start,'$lte':end}},
                {key:1 for key in RAW_FIELDS}).sort([('received_at',1),('_id',1)]).limit(args.max_rows+1).batch_size(200).max_time_ms(10000)
            for row in cursor:
                count+=1
                if count>args.max_rows:raise ValueError('Export exceeds explicit maximum; narrow the range')
                record=raw_record(row)
                for key in ['measured_at','received_at']:record[key]=record[key].isoformat()
                writer.writerow(record)
        temporary.rename(args.output)
        args.output.with_suffix('.manifest.json').write_text(json.dumps(dict(source='verified MongoDB measurements',
            rows=count,devices=args.device,start=start.isoformat(),end=end.isoformat(),sha256=file_hash(args.output),
            labelled=False,mode='RESEARCH',quality='No independent anomaly ground truth'),indent=2)+'\n')
        print('Bounded unlabelled telemetry export complete; rows:',count)
    finally:repo.close()

if __name__=='__main__':main()

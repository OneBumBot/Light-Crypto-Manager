"""Explicit synthetic fixture generation, never a replacement for Edge-IIoTset."""
import argparse
from datetime import datetime,timedelta,timezone
import json
import math
import os
from pathlib import Path
import csv
from src.telemetry import DEVICE
from .telemetry_features import RAW_FIELDS


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--synthetic-demo',action='store_true',required=True)
    parser.add_argument('--device',action='append',required=True)
    parser.add_argument('--rows-per-device',type=int,default=80)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--config-output',type=Path,required=True)
    args=parser.parse_args()
    if not 40<=args.rows_per_device<=1000 or len(args.device)>32 or len(set(args.device))!=len(args.device) or any(not DEVICE.fullmatch(d) for d in args.device):
        parser.error('Invalid bounded demo specification')
    os.umask(0o077);args.output.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    with args.output.open('x') as stream:
        writer=csv.DictWriter(stream,fieldnames=RAW_FIELDS);writer.writeheader()
        origin=datetime(2026,1,1,tzinfo=timezone.utc)
        for i in range(args.rows_per_device):
            for j,device in enumerate(args.device):
                date=origin+timedelta(seconds=i*10)
                writer.writerow(dict(device_id=device,key_epoch=1,sequence_number=i+1,
                    measured_at=date.isoformat(),received_at=(date+timedelta(milliseconds=100)).isoformat(),
                    temperature=20+j*15+math.sin(i/4),humidity=35+j*10+math.cos(i/6)))
    settings=dict(config_version=1,mode='DEMO',source='EXPLICIT SYNTHETIC INTEGRATION FIXTURE; NOT REAL SENSOR BASELINE',
        license_status='Project-generated synthetic fixture',synthetic=True,random_state=42,max_rows=32000,
        model_id='telemetry-statistical',model_version='1.0.0',task='telemetry_anomaly',algorithm='statistical',
        feature_version='telemetry-causal-v1',split_strategy='time',time_column='received_at',group_column=None,
        fractions=[0.6,0.2,0.2],window=5,expected_interval=10,validation_alert_quantile=0.99)
    with args.config_output.open('x') as stream:json.dump(settings,stream,indent=2)
    print('Synthetic demo fixture rows:',len(args.device)*args.rows_per_device)

if __name__=='__main__':main()

"""Frozen baseline validation inference cost only; no fitting or quality/threshold selection."""
import argparse
import gc
import json
from pathlib import Path
import platform
import resource
import time
import numpy as np
import pandas as pd
from src.classifier.ml.artifacts import file_hash,load,versions
from src.classifier.ml.network import risk_scores


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--data',type=Path,required=True);p.add_argument('--models',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    frame=pd.read_csv(args.data);results=[]
    for path in sorted(args.models.glob('*/1.0.0/manifest.json')):
        info=json.loads(path.read_text());manifest,pipe=load(args.models,info['model_id'],info['model_version'])
        if manifest['dataset']['sha256']!=file_hash(args.data):raise ValueError('Frozen data mismatch')
        validation=frame.iloc[manifest['split']['indices'][1]]
        risk_scores(pipe,validation.iloc[:16],manifest['algorithm'])
        latency=[]
        for index in range(min(64,len(validation))):
            start=time.perf_counter();risk_scores(pipe,validation.iloc[[index]],manifest['algorithm']);latency.append((time.perf_counter()-start)*1000)
        start=time.perf_counter()
        for index in range(0,len(validation),256):risk_scores(pipe,validation.iloc[index:index+256],manifest['algorithm'])
        elapsed=time.perf_counter()-start
        results.append(dict(model_id=manifest['model_id'],model_version=manifest['model_version'],artifact_sha256=manifest['artifact_sha256'],
            artifact_bytes=(path.parent/'model.joblib').stat().st_size,feature_version=manifest['feature_version'],
            rows=len(validation),scope='frozen stage6 validation; no test rows',single_samples=len(latency),single_ms_p50_p95_p99=np.quantile(latency,[.5,.95,.99]).tolist(),
            batch_size=256,throughput_rows_per_second=len(validation)/elapsed,
            peak_rss_kib_cumulative_process=int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),
            fit_performed=False,threshold_changed=False,training_time_seconds=None,preprocessing_fit_seconds=None))
        del pipe;gc.collect()
    result=dict(schema_version=1,versions=versions(),architecture=platform.machine(),system=platform.system(),dataset_sha256=file_hash(args.data),
        data_scope='historical validation only',results=results,
        limitations=['Small shared development host timing, not controlled production benchmark','Schema validation/preprocessing included in inference',
                    'Cumulative process RSS, not isolated per-model memory','No Raspberry Pi/ARM measurement','No new model quality or improvement claim'])
    with args.output.open('x') as stream:json.dump(result,stream,indent=2,allow_nan=False)
    print('Frozen baseline validation inference costs saved; training/test/thresholds unchanged')

if __name__=='__main__':main()

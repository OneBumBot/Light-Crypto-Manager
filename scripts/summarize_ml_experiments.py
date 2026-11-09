"""Publish aggregates of frozen research runs; no weights, raw rows or node IDs."""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.metrics import f1_score
from src.classifier.ml.artifacts import load,file_hash
from src.classifier.ml.network import risk_scores
from src.classifier.ml.metrics import classification_metrics

ATTACK_TYPES=['Normal','MITM','Uploading','Ransomware','SQL_injection','DDoS_HTTP','DDoS_TCP',
    'Password','Port_Scanning','Vulnerability_scanner','Backdoor','XSS','Fingerprinting','DDoS_UDP','DDoS_ICMP']


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--models-dir',required=True);parser.add_argument('--data',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    frame=pd.read_csv(args.data,low_memory=False);runs=[]
    for model_id in ['edge-network-rf-binary','edge-network-rf-multiclass','edge-network-if']:
        manifest,pipeline=load(args.models_dir,model_id,'1.0.0')
        if manifest['dataset']['sha256']!=file_hash(args.data):raise ValueError('Frozen experiment dataset mismatch')
        train,validation,test=manifest['split']['indices']
        held=frame.loc[test]
        scores=risk_scores(pipeline,held,manifest['algorithm'])
        risk=classification_metrics(held.Attack_label,(scores>=manifest['threshold']).astype(int),scores)
        quality=dict(manifest['metrics'])
        if manifest['algorithm']=='rf_multiclass':
            quality['macro_f1_fixed_15_class_ontology']=float(f1_score(held.Attack_type,pipeline.predict(held),labels=ATTACK_TYPES,average='macro',zero_division=0))
        run=dict(model_id=model_id,model_version='1.0.0',algorithm=manifest['algorithm'],mode=manifest['mode'],
            artifact_sha256=manifest['artifact_sha256'],dataset=manifest['dataset'],
            split_counts=manifest['split']['counts'],feature_overlap_purged=manifest['split'].get('duplicate_purged_rows'),
            fit_rows=manifest['preprocessing']['fit_rows'],threshold=manifest['threshold'],metrics=quality,
            risk_signal_metrics=risk,versions=manifest['versions'],preprocessing=manifest['preprocessing'],
            split_class_distribution={name:{str(k):int(v) for k,v in frame.loc[idx].Attack_type.value_counts().items()}
                                      for name,idx in [('train',train),('validation',validation),('test',test)]},
            test_classes_absent_from_train=sorted(set(held.Attack_type)-set(frame.loc[train].Attack_type)),
            limitations=manifest['limitations']+manifest['dataset']['parent']['limitations'])
        runs.append(run)
    with args.output.open('x') as stream:json.dump(dict(report_version=1,synthetic=False,runs=runs,
        scientific_scope='Limited real-data host-pair proxy holdout; not device-independent or production attack detection',
        fit_or_threshold_tuning_performed=False),stream,indent=2,allow_nan=False)
    for run in runs:
        m=run['metrics'];print(run['model_id'], 'fit',run['fit_rows'],'macro-F1',m['macro_f1'],
            'FPR',m['false_positive_rate'],'PR-AUC',m['pr_auc'],'ROC-AUC',m['roc_auc'])

if __name__=='__main__':main()

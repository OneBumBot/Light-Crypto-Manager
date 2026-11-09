"""Explicit-path research training. Never substitutes synthetic data for a missing dataset."""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
from .artifacts import export, file_hash, load
from .schema import NETWORK_VERSION, TELEMETRY_VERSION, NETWORK_FEATURES
from .network import build_network, risk_scores
from .telemetry_features import causal_frame, build_telemetry
from .splitting import split_frame
from .metrics import classification_metrics, choose_threshold


def read_config(path):
    from src.telemetry import strict_json
    value=strict_json(Path(path).read_bytes())
    if value.get('config_version')!=1: raise ValueError('Unsupported training config version')
    if value.get('mode') not in ['DEMO','RESEARCH']: raise ValueError('Explicit DEMO/RESEARCH mode required')
    if type(value.get('random_state')) is not int: raise ValueError('Explicit integer random_state required')
    if not value.get('source') or not value.get('license_status'):
        raise ValueError('Dataset provenance and license status required')
    return value


def read_data(path,config):
    path=Path(path)
    if not path.is_file(): raise ValueError('Dataset file missing; provide an explicit existing --data path')
    maximum=config.get('max_rows',300000)
    if type(maximum) is not int or not 10<=maximum<=10000000: raise ValueError('Invalid max_rows')
    frame=pd.read_csv(path,nrows=maximum+1,low_memory=False)
    if len(frame)>maximum: raise ValueError('Dataset exceeds explicit max_rows resource limit')
    if not frame.index.is_unique or frame.columns.duplicated().any() or len(frame)<10:
        raise ValueError('Insufficient data or duplicate columns')
    return frame, {'name':config['source'],'sha256':file_hash(path),'rows':len(frame),
        'columns':list(frame.columns),'dtypes':{k:str(v) for k,v in frame.dtypes.items()},
        'devices':int(frame.device_id.nunique()) if 'device_id' in frame else None,
        'license_status':config['license_status'],'synthetic':bool(config.get('synthetic',False))}


def train(data,config,models_dir):
    frame,source=read_data(data,config)
    if config.get('source_manifest'):
        parent=json.loads(Path(config['source_manifest']).read_text())
        if parent['prepared_sha256']!=source['sha256']:raise ValueError('Prepared-data parent hash mismatch')
        source['parent']=parent
    task=config['task']; algorithm=config['algorithm']
    if task=='network_ids':
        if config['feature_version']!=NETWORK_VERSION: raise ValueError('Unsupported network schema')
        if not {'Attack_label','Attack_type'}<=set(frame): raise ValueError('Attack targets are required')
        binary=pd.to_numeric(frame.Attack_label,errors='raise')
        if binary.isna().any() or not binary.isin([0,1]).all(): raise ValueError('Binary labels must be exactly 0/1')
        types=frame.Attack_type
        if types.isna().any() or not types.map(lambda x:type(x) is str and 0<len(x.strip())<=80).all():
            raise ValueError('Invalid attack categories')
        types=types.str.strip()
        if ((binary==0)!=(types=='Normal')).any(): raise ValueError('Contradictory normal/attack targets')
        source['class_distribution']={str(k):int(v) for k,v in types.value_counts().items()}
        partitions,split=split_frame(frame,config)
        train_idx,val_idx,test_idx=partitions
        # Optional exact-feature overlap guard: fail instead of silently altering the held-out sample.
        hashes=pd.util.hash_pandas_object(frame[NETWORK_FEATURES],index=False)
        overlap=len(set(hashes.loc[train_idx]) & (set(hashes.loc[val_idx])|set(hashes.loc[test_idx])))
        split['exact_feature_overlap_train_holdouts']=overlap
        sets=[set(hashes.loc[p]) for p in partitions]
        crossing=(sets[0]&sets[1])|(sets[0]&sets[2])|(sets[1]&sets[2])
        if crossing and config.get('feature_overlap_policy')=='purge_all_cross_partition':
            partitions=[p[~hashes.loc[p].isin(crossing).to_numpy()] for p in partitions]
            if any(len(p)==0 for p in partitions):raise ValueError('Empty partition after prespecified duplicate purge')
            train_idx,val_idx,test_idx=partitions
            split['duplicate_purged_rows']=sum(split['counts'].values())-sum(map(len,partitions))
            split['counts']=dict(zip(['train','validation','test'],map(len,partitions)))
            import hashlib
            split['indices_sha256']=[hashlib.sha256(','.join(map(str,p)).encode()).hexdigest() for p in partitions]
            split['indices']=[list(map(int,p)) for p in partitions]
        elif crossing and config.get('reject_feature_overlap',True):raise ValueError('Feature duplicate overlap across partitions')
        y=types if algorithm=='rf_multiclass' else binary.astype(int)
        pipeline=build_network(algorithm,config['random_state'],config.get('trees',100))
        if algorithm=='isolation_forest': fit_idx=train_idx[binary.loc[train_idx].to_numpy()==0]
        else: fit_idx=train_idx
        if len(fit_idx)<10: raise ValueError('Insufficient training rows')
        if algorithm!='isolation_forest' and y.loc[fit_idx].nunique()<2: raise ValueError('Training requires multiple classes')
        if not (binary.loc[fit_idx]==0).any(): raise ValueError('Training normal class missing')
        pipeline.fit(frame.loc[fit_idx],None if algorithm=='isolation_forest' else y.loc[fit_idx])
        threshold=choose_threshold(binary.loc[val_idx],risk_scores(pipeline,frame.loc[val_idx],algorithm),config.get('validation_fpr_target',0.05))
        scores=risk_scores(pipeline,frame.loc[test_idx],algorithm)
        prediction=pipeline.predict(frame.loc[test_idx]) if algorithm=='rf_multiclass' else (scores>=threshold).astype(int)
        metrics=classification_metrics(y.loc[test_idx],prediction,scores,normal='Normal' if algorithm=='rf_multiclass' else 0)
        feature_version=NETWORK_VERSION
        conditions={'feature_order':NETWORK_FEATURES,'preprocessing':'ColumnTransformer: train-only median/scaler and bounded OHE with unknown-ignore',
            'fit_rows':len(fit_idx),'threshold_selection':'validation only, F1 subject to normal-validation FPR bound',
            'score_semantics':'higher means more anomalous; IF negative score_samples, RF 1-P(normal); not calibrated attack probability',
            'score_range':[0,1],'future_collector_required':True}
    elif task=='telemetry_anomaly':
        if config['feature_version']!=TELEMETRY_VERSION: raise ValueError('Unsupported telemetry schema')
        window=config.get('window',8); interval=config.get('expected_interval',10)
        features,statuses=causal_frame(frame.to_dict('records'),window,interval)
        if len(features)<15: raise ValueError('Insufficient causal training windows')
        features=features.reset_index(drop=True)
        split_config={**config,'split_strategy':'time','time_column':'received_at','time_format':'ISO8601','group_column':None}
        partitions,split=split_frame(features,split_config)
        train_idx,val_idx,test_idx=partitions
        pipeline=build_telemetry(algorithm,config['random_state'],config.get('trees',100))
        pipeline.fit(features.loc[train_idx])
        scores_val=-pipeline.score_samples(features.loc[val_idx])
        target=config.get('validation_alert_quantile',0.99)
        if not 0.5<=target<1: raise ValueError('Invalid validation alert quantile')
        threshold=float(np.quantile(scores_val,target))
        scores=-pipeline.score_samples(features.loc[test_idx])
        metrics={'labelled_quality_available':False,'reason':'No independently verified telemetry labels',
            'test_objects':len(test_idx),'alert_rate':float((scores>=threshold).mean()),
            'score_min':float(scores.min()),'score_max':float(scores.max())}
        source['time_range']=[min(row['received_at'] for row in frame.to_dict('records')),
                              max(row['received_at'] for row in frame.to_dict('records'))]
        from .telemetry_features import FEATURES
        conditions={'feature_order':FEATURES,'preprocessing':'causal past-only windows + train-only robust per-device baseline; IF train-only imputer/scaler',
            'window':window,'expected_interval':interval,'fit_rows':len(train_idx),
            'warmup_or_skipped':len(statuses)-len(features),'threshold_selection':'unlabelled validation alert quantile; not measured FPR',
            'score_semantics':'higher means more anomalous; max robust deviation for statistical, negative score_samples for IF; not attack probability',
            'score_range':[0,None] if algorithm=='statistical' else [0,1]}
        feature_version=TELEMETRY_VERSION
    else: raise ValueError('Unsupported ML task')
    metadata=dict(task=task,algorithm=algorithm,feature_version=feature_version,mode=config['mode'],
        dataset=source,training_parameters=config,random_state=config['random_state'],
        preprocessing=conditions,threshold=threshold,metrics=metrics,split=split,
        limitations=['research model, not a trusted cyberattack detector','no online network feature collector','quality does not transfer from synthetic tests to real attacks'])
    return export(models_dir,config['model_id'],config['model_version'],pipeline,metadata)


def evaluate(data,evaluation_config,models_dir,model_id,model_version):
    """Separate frozen-artifact evaluation; never fit transforms or alter threshold."""
    config=read_config(evaluation_config)
    manifest,pipeline=load(models_dir,model_id,model_version)
    frame,source=read_data(data,config)
    if source['sha256']==manifest['dataset']['sha256']:
        raise ValueError('External evaluation requires a separate dataset; original holdout is in training manifest')
    if manifest['task']=='network_ids':
        binary=pd.to_numeric(frame.Attack_label,errors='raise')
        if not binary.isin([0,1]).all() or ((binary==0)!=(frame.Attack_type=='Normal')).any():
            raise ValueError('Invalid evaluation targets')
        scores=risk_scores(pipeline,frame,manifest['algorithm'])
        multiclass=manifest['algorithm']=='rf_multiclass'
        prediction=pipeline.predict(frame) if multiclass else (scores>=manifest['threshold']).astype(int)
        metrics=classification_metrics(frame.Attack_type if multiclass else binary,prediction,scores,normal='Normal' if multiclass else 0)
    else:
        settings=manifest['preprocessing']
        features,statuses=causal_frame(frame.to_dict('records'),settings['window'],settings['expected_interval'])
        if features.empty: raise ValueError('No evaluation windows')
        scores=-pipeline.score_samples(features)
        metrics=dict(labelled_quality_available=False,objects=len(features),alert_rate=float((scores>=manifest['threshold']).mean()),
                     skipped=len(statuses)-len(features))
    return dict(model_id=model_id,model_version=model_version,artifact_sha256=manifest['artifact_sha256'],
                dataset=source,threshold=manifest['threshold'],metrics=metrics,fit_performed=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['train','evaluate'])
    parser.add_argument('--data',required=True)
    parser.add_argument('--config',required=True)
    parser.add_argument('--models-dir',required=True)
    parser.add_argument('--model-id');parser.add_argument('--model-version')
    parser.add_argument('--report')
    args=parser.parse_args()
    try:
        if args.command=='train': result=train(args.data,read_config(args.config),args.models_dir)
        else:
            if not args.model_id or not args.model_version: raise ValueError('Evaluation model identity required')
            result=evaluate(args.data,args.config,args.models_dir,args.model_id,args.model_version)
        if args.report:
            path=Path(args.report)
            with path.open('x') as stream: json.dump(result,stream,indent=2,allow_nan=False)
            path.chmod(0o600)
        print(json.dumps({'task':result.get('task'),'model_id':result.get('model_id'),
            'model_version':result.get('model_version'),'mode':result.get('mode'),'dataset_sha256':result['dataset']['sha256'],
            'rows':result['dataset']['rows'],'status':'research experiment completed'},allow_nan=False))
    except (ValueError,KeyError,FileNotFoundError) as error:
        parser.exit(2,'ML experiment rejected: '+str(error)+'\n')

if __name__=='__main__': main()

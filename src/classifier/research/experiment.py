"""Controlled RF/IF candidates, validation-only selection and single frozen test entry."""
from src.research_stand.quality import statuses
import gc
import json
import os
from pathlib import Path
import resource
import time
import numpy as np
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler,RobustScaler
from sklearn.ensemble import RandomForestClassifier,IsolationForest
from sklearn.metrics import classification_report,confusion_matrix,f1_score
from src.classifier.ml.artifacts import export,load,versions,file_hash
from .schema import VERSION,FEATURES,PacketSchema,FeatureSubset,packet_frame
from .datasets import read_prepared,canonical_hash,LABELS
from .splitting import prepare_split
from .metrics import operating_point,binary_metrics,cluster_intervals,scores_checked


def candidates():
    common=dict(n_estimators=100,max_depth=None,min_samples_split=2,min_samples_leaf=1,max_features='sqrt')
    rf=[dict(candidate_id=name,algorithm='rf',scaling='none',parameters=dict(common,class_weight=weight)) for name,weight in
        [('rf_baseline',None),('rf_balanced','balanced'),('rf_subsample','balanced_subsample')]]
    rf += [dict(candidate_id='rf_tuned_'+str(i),algorithm='rf',scaling='none',parameters=dict(
        n_estimators=trees,max_depth=depth,min_samples_leaf=leaf,min_samples_split=split,max_features=features,class_weight=weight))
        for i,(trees,depth,leaf,split,features,weight) in enumerate([
            (100,16,2,4,'sqrt','balanced'),(200,32,4,8,.8,'balanced_subsample')])]
    forest=[dict(candidate_id=name,algorithm='if',scaling=scale,parameters=dict(n_estimators=trees,max_samples=samples,max_features=features))
        for name,trees,samples,features,scale in [('if_baseline',100,256,1.0,'none'),('if_standard',100,256,1.0,'standard'),
            ('if_tuned_0',200,1024,.75,'none'),('if_tuned_1',200,256,.5,'robust')]]
    return rf+forest


def config_checked(config):
    if type(config) is not dict:raise ValueError('Research config object required')
    from src.classifier.ml.schema import safe_name
    safe_name(config.get('model_version','7.5.0'))
    if type(config.get('schema_version')) is not int or config['schema_version']!=1 or type(config.get('seed')) is not int or not 0<=config['seed']<2**32:raise ValueError('Unsupported research config')
    if type(config.get('validation_fpr_target',.05)) not in (float,int) or not 0<config.get('validation_fpr_target',.05)<1:raise ValueError('Invalid validation target')
    trials=config.get('candidates',candidates())
    if type(trials) is not list or not 1<=len(trials)<=(24 if config.get('study_contract')=='stage14-offline-v1' else 16):raise ValueError('Bounded candidate matrix required')
    ids=set()
    for item in trials:
        from src.classifier.ml.schema import safe_name
        name=safe_name(item['candidate_id'])
        if name in ids:raise ValueError('Duplicate candidate ID')
        ids.add(name)
        if item['algorithm'] not in {'rf','if'} or item['scaling'] not in {'none','standard','robust'}:raise ValueError('Unknown model/scaling')
        selected=item.get('features',FEATURES)
        if type(selected) is not list or not selected or not all(type(v) is str for v in selected) or len(selected)!=len(set(selected)) or not set(selected)<=set(FEATURES):raise ValueError('Only preregistered passive features allowed')
        p=item['parameters'];allowed={'n_estimators','max_depth','min_samples_split','min_samples_leaf','max_features','class_weight'} if item['algorithm']=='rf' else {'n_estimators','max_samples','max_features'}
        if set(p)-allowed:raise ValueError('Unsupported hyperparameter')
        if type(p.get('n_estimators')) is not int or not 1<=p['n_estimators']<=256:raise ValueError('Tree count exceeds resource limit')
        if p.get('class_weight') not in {None,'balanced','balanced_subsample'}:raise ValueError('Unsupported balancing')
        if p.get('max_depth') is not None and (type(p['max_depth']) is not int or not 1<=p['max_depth']<=64):raise ValueError('Invalid depth')
        for field in ['min_samples_leaf','min_samples_split']:
            if field in p and (type(p[field]) is not int or not (2 if field=='min_samples_split' else 1)<=p[field]<=128):raise ValueError('Invalid sample hyperparameter')
        features=p.get('max_features',1.0)
        if features!='sqrt' and (type(features) not in (int,float) or not 0<features<=1):raise ValueError('Invalid max_features')
        if item['algorithm']=='if' and (type(p.get('max_samples')) is not int or not 2<=p['max_samples']<=4096):raise ValueError('Invalid IF max_samples')
    return trials


def risk(pipeline,X,algorithm):
    if algorithm=='if':return scores_checked(-pipeline.score_samples(X))
    classes=list(pipeline.classes_);normal='Normal' if 'Normal' in classes else 0
    if normal not in classes:raise ValueError('Fitted normal class missing')
    return scores_checked(1-pipeline.predict_proba(X)[:,classes.index(normal)])


def fit_candidate(frame,indices,spec,seed,multiclass=False):
    sub=frame.iloc[indices]
    if spec['algorithm']=='if':sub=sub.loc[sub.label==0]
    if len(sub)<2 or sub.label.nunique()<2 and spec['algorithm']=='rf':raise ValueError('Insufficient model fit classes')
    if packet_frame(sub).notna().sum().min()==0:raise ValueError('All-missing training feature; no invented zero column')
    steps=[('schema',PacketSchema()),('features',FeatureSubset(spec.get('features',FEATURES))),('impute',SimpleImputer(strategy='median',add_indicator=True,keep_empty_features=True))]
    if spec['scaling']!='none':steps.append(('scale',StandardScaler() if spec['scaling']=='standard' else RobustScaler()))
    prefix=Pipeline(steps);start=time.perf_counter();matrix=prefix.fit_transform(sub);preparation=time.perf_counter()-start
    model=(RandomForestClassifier(random_state=seed,n_jobs=1,**spec['parameters']) if spec['algorithm']=='rf' else
           IsolationForest(random_state=seed,n_jobs=1,contamination='auto',**spec['parameters']))
    target=None if spec['algorithm']=='if' else (sub.attack_type if multiclass else sub.label)
    start=time.perf_counter();model.fit(matrix,target);fit_time=time.perf_counter()-start
    return Pipeline(prefix.steps+[('model',model)]),dict(fit_rows=len(sub),fit_normal=int((sub.label==0).sum()),
        fit_attack=int((sub.label==1).sum()),fit_attack_types=sorted(set(sub.attack_type)),preprocessing_fit_seconds=preparation,estimator_fit_seconds=fit_time,
        peak_rss_kib_cumulative_process=int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss))


def source_split(frame,source,config):
    if source.get('dataset_version')=='stage14-lightcrypto-lab-v1':
        from src.research_stand.stage14 import linked_split
        return linked_split(frame,source['stage14_group_partitions'],config.get('minimum_normal_rows',1000),config.get('minimum_class_captures',5))
    return prepare_split(frame,config['seed'],config.get('minimum_normal_rows',1000),config.get('minimum_class_captures',5))


def plan(data,manifest,config,output):
    config_checked(config);frame,source=read_prepared(data,manifest,config.get('max_rows',100000))
    if source.get('dataset_family')=='lightcrypto-lab-v1' and source.get('label_rules_version') and not source.get('provenance',{}).get('independent_label_verification'):raise ValueError('No independently corroborated laboratory labels; planning blocked')
    from src.research_stand.stage14 import training_gate
    training_gate(data,manifest)
    if source.get('dataset_version')=='stage14-lightcrypto-lab-v1' and config.get('study_contract')!='stage14-offline-v1':raise ValueError('Explicit Stage14 offline study contract required')
    split=source_split(frame,source,config)
    value=dict(schema_version=1,dataset_sha256=source['sha256'],manifest_sha256=file_hash(Path(manifest)),
        config=config,config_sha256=canonical_hash(config),split=split,versions=versions())
    value['plan_sha256']=canonical_hash(value)
    with Path(output).open('x') as stream:json.dump(value,stream,indent=2,allow_nan=False)
    return value


def checked_plan(data,manifest,plan_path):
    p=json.loads(Path(plan_path).read_text());digest=p.pop('plan_sha256')
    if canonical_hash(p)!=digest:raise ValueError('Frozen plan modified')
    p['plan_sha256']=digest
    frame,source=read_prepared(data,manifest,p['config'].get('max_rows',100000))
    from src.research_stand.stage14 import training_gate
    training_gate(data,manifest)
    if p['dataset_sha256']!=source['sha256'] or p['manifest_sha256']!=file_hash(Path(manifest)) or p['versions']!=versions():raise ValueError('Plan provenance/version mismatch')
    if canonical_hash(p['config'])!=p['config_sha256']:raise ValueError('Configuration changed')
    actual=source_split(frame,source,p['config'])
    if actual!=p['split']:raise ValueError('Frozen partition mismatch')
    return frame,source,p


def train(data,manifest,plan_path,models_dir,experiment_dir):
    frame,source,p=checked_plan(data,manifest,plan_path);config=p['config'];trials=config_checked(config)
    if source.get('dataset_family')=='lightcrypto-lab-v1' and not source.get('label_rules_version'):raise ValueError('Archived laboratory v1 is not approved for training')
    folder=Path(experiment_dir);folder.mkdir(mode=0o700,parents=True,exist_ok=False)
    train_idx,val_idx,_=p['split']['indices'];validation=frame.iloc[val_idx]
    results=[]
    for spec in trials:
        for multi in ([False,True] if spec['algorithm']=='rf' and config.get('include_multiclass',True) else [False]):
            pipeline,timing=fit_candidate(frame,train_idx,spec,config['seed'],multi)
            scores=risk(pipeline,validation,spec['algorithm']);point=operating_point(validation.label,scores,config.get('validation_fpr_target',.05))
            metrics=binary_metrics(validation.label,scores,point['threshold'],validation.attack_type,timing['fit_attack_types'])
            session_calibration=None;validation_distribution=None
            if source.get('dataset_version')=='stage14-lightcrypto-lab-v1':
                from .group_metrics import calibrate,distribution
                session_calibration=calibrate(validation,scores,point['threshold'],config.get('validation_fpr_target',.05));validation_distribution=distribution(scores)
            validation_multiclass=None
            if multi:
                labels=source['class_ontology'];prediction=pipeline.predict(validation)
                validation_multiclass=dict(macro_f1_fixed_ontology=float(f1_score(validation.attack_type,prediction,labels=labels,average='macro',zero_division=0)),
                    ontology=labels,unseen_validation_categories=sorted(set(validation.attack_type)-set(pipeline.classes_)),scope='argmax types; not thresholded risk')
            mid='research75-'+spec['candidate_id']+('-multiclass' if multi else '-binary');version=config.get('model_version','7.5.0')
            metadata=dict(task='network_ids',algorithm='isolation_forest' if spec['algorithm']=='if' else ('rf_multiclass' if multi else 'rf_binary'),
                feature_version=VERSION,mode='DEMO' if source['synthetic'] else 'RESEARCH',trusted_detector=False,
                dataset=source,training_parameters=dict(spec,seed=config['seed']),random_state=config['seed'],
                preprocessing=dict(feature_order=FEATURES,selected_features=spec.get('features',FEATURES),scaling=spec['scaling'],imputer='train-only median + missing indicators',
                    score_range=[0,1],score_semantics='Higher means more anomalous, not attack probability',fit_rows=timing['fit_rows'],future_collector_required=True),
                threshold=point['threshold'],metrics={'validation_binary_risk':metrics},split={'plan_sha256':p['plan_sha256'],'sha256':p['split']['sha256']},
                limitations=['Offline research only','No trusted online network collector','Connection/window corroboration is not per-packet attack ground truth','No live control; single-host domain'])
            exported=export(models_dir,mid,version,pipeline,metadata)
            results.append(dict(candidate_id=spec['candidate_id'],ablation=spec.get('ablation',False),session_calibration=session_calibration,validation_score_distribution=validation_distribution,algorithm=spec['algorithm'],multiclass=multi,model_id=mid,model_version=version,
                artifact_sha256=exported['artifact_sha256'],threshold=point,validation=metrics,validation_multiclass=validation_multiclass,timing=timing))
            del pipeline;gc.collect()
    # All predefined baseline/balanced comparisons are frozen; winner chosen only on validation.
    winners={}
    for task in ['rf_binary','rf_multiclass','if']:
        rows=[r for r in results if not r.get('ablation') and ('if' if r['algorithm']=='if' else ('rf_multiclass' if r['multiclass'] else 'rf_binary'))==task]
        if rows:winners[task]=max(rows,key=lambda r:((r['validation_multiclass']['macro_f1_fixed_ontology'] if task=='rf_multiclass' else r['validation']['f1']),-r['validation']['fpr'],r['candidate_id']))['model_id']
    if source.get('dataset_version')=='stage14-lightcrypto-lab-v1':
        for algorithm in ['rf','if']:
            rows=[r for r in results if r['algorithm']==algorithm and not r.get('ablation')]
            winners[algorithm+'_session']=max(rows,key=lambda r:(r['session_calibration']['selected']['validation']['f1'],-r['session_calibration']['selected']['validation']['fpr'],r['candidate_id']))['model_id']
    freeze=dict(schema_version=1,plan_sha256=p['plan_sha256'],dataset_sha256=source['sha256'],models=results,winners=winners,
        mode='DEMO' if source['synthetic'] else 'RESEARCH',synthetic=source['synthetic'],fit_performed=True,test_evaluated=False,versions=versions())
    freeze['sha256']=canonical_hash(freeze)
    (folder/'freeze.json').write_text(json.dumps(freeze,indent=2,allow_nan=False)+'\n')
    return freeze


def final_test(data,manifest,plan_path,models_dir,experiment_dir):
    frame,source,p=checked_plan(data,manifest,plan_path);folder=Path(experiment_dir)
    frozen=json.loads((folder/'freeze.json').read_text());expected=frozen.pop('sha256')
    if canonical_hash(frozen)!=expected or frozen['plan_sha256']!=p['plan_sha256']:raise ValueError('Experiment freeze mismatch')
    # Exclusive durable entry records a test attempt before any prediction. Crashes require reviewed new experiment, not retuning.
    fd=os.open(folder/'final-test-started',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as stream:stream.write(expected+'\n')
    test=frame.iloc[p['split']['indices'][2]];reports=[]
    for row in frozen['models']:
        model,pipeline=load(models_dir,row['model_id'],row['model_version'])
        if model['artifact_sha256']!=row['artifact_sha256'] or model['threshold']!=row['threshold']['threshold']:raise ValueError('Frozen model/threshold modified')
        scores=risk(pipeline,test,row['algorithm']);threshold=model['threshold']
        metrics=binary_metrics(test.label,scores,threshold,test.attack_type,row['timing']['fit_attack_types'])
        if source.get('dataset_version')=='stage14-lightcrypto-lab-v1':
            from .group_metrics import evaluation
            metrics['stage14']=evaluation(test,scores,threshold,row['session_calibration'],p['config']['seed']);metrics['uncertainty']=metrics['stage14']['packet_cluster_uncertainty']
        else:metrics['uncertainty']=cluster_intervals(test.label,(scores>=threshold).astype(int),test.capture_id,p['config']['seed'])
        if row['multiclass']:
            pred=pipeline.predict(test);labels=source['class_ontology']
            metrics['multiclass']=dict(ontology=labels,macro_f1_fixed_ontology=float(f1_score(test.attack_type,pred,labels=labels,average='macro',zero_division=0)),
                confusion_matrix=confusion_matrix(test.attack_type,pred,labels=labels).tolist(),
                classification_report=classification_report(test.attack_type,pred,labels=labels,output_dict=True,zero_division=0),
                unseen_test_categories=sorted(set(test.attack_type)-set(pipeline.classes_)),scope='argmax types, separate from binary thresholded risk')
        latencies=[]
        for i in range(min(64,len(test))):
            start=time.perf_counter();risk(pipeline,test.iloc[[i]],row['algorithm']);latencies.append((time.perf_counter()-start)*1000)
        start=time.perf_counter()
        for index in range(0,len(test),256):risk(pipeline,test.iloc[index:index+256],row['algorithm'])
        elapsed=time.perf_counter()-start
        report=dict(model_id=row['model_id'],model_version=row['model_version'],artifact_sha256=model['artifact_sha256'],metrics=metrics,
            inference=dict(single_packet_ms_p50_p95_p99=np.quantile(latencies,[.5,.95,.99]).tolist(),single_samples=len(latencies),
                           batch_size=256,throughput_packets_per_second=len(test)/max(elapsed,1e-12),
                           peak_rss_kib_cumulative_process=int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)),
            threshold=threshold,threshold_frozen=True,mode=model['mode'],trusted_detector=False)
        reports.append(report)
    output=dict(schema_version=1,scope='final_internal_test',dataset=source,split=p['split'],freeze_sha256=expected,
        scientific_quality_available=False, data_quality=statuses(source),versions=versions(),results=reports,
        limitations=['Capture independence is a data collection assumption; not proven by different IDs',
                     'TLS availability of fields is not encrypted-runtime generalization','Synthetic results are engineering tests only'])
    (folder/'test.json').write_text(json.dumps(output,indent=2,allow_nan=False)+'\n')
    return output

"""Synthetic engineering fixtures only. These tests are not attack-detection benchmarks."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from src.classifier.research.schema import VERSION,FEATURES,packet_frame
from src.classifier.research.datasets import import_csv,read_prepared,mapping,canonical_hash
from src.classifier.research.splitting import prepare_split
from src.classifier.research.experiment import plan,train,final_test,fit_candidate,config_checked
from src.classifier.research.metrics import operating_point,binary_metrics,cluster_intervals
from src.classifier.research.inference import predict
from src.classifier.ml.artifacts import file_hash,load


def fixture(tmp_path,captures=30):
    files=[]
    for group in range(captures):
        n=12;attack=group%2==1;i=np.arange(n)+group*n
        data=pd.DataFrame({'frame.len':100+i,'tcp.len':20+i,'tcp.flags':np.where(i%2,16,2),
            'tcp.window_size_value':1000+i,'tcp.time_delta':i/10000+0.001,
            'frame.time_epoch':1700000000+i,'frame.number':np.arange(n)+1,'tcp.stream':np.arange(n)//3,'ip.proto':6})
        path=tmp_path/('raw'+str(group)+'.csv');data.to_csv(path,index=False)
        files.append(dict(path=str(path),capture_id='cap'+str(group),source_id='synthetic',sha256=file_hash(path),attack_type='dos' if attack else 'legitimate'))
    config=dict(schema_version=1,granularity='packet',feature_version=VERSION,synthetic=True,source_url='synthetic://unit-only',
        dataset_version='fixture1',license='project synthetic fixture',label_scope='synthetic_fixture',files=files)
    output=tmp_path/'prepared.csv';import_csv(config,output)
    return output,output.with_suffix('.manifest.json'),config


def settings():
    return dict(schema_version=1,seed=75,minimum_normal_rows=3,minimum_class_captures=1,
        candidates=[dict(candidate_id='rf_test',algorithm='rf',scaling='standard',parameters=dict(n_estimators=4,class_weight='balanced')),
                    dict(candidate_id='if_test',algorithm='if',scaling='none',parameters=dict(n_estimators=4,max_samples=32,max_features=1.0))])


def test_import_provenance_granularity_mapping_and_missing(tmp_path):
    data,manifest,config=fixture(tmp_path)
    f,m=read_prepared(data,manifest);assert len(f)==360 and m['synthetic'] and m['captures']==30
    assert mapping('legitimate')==('Normal',0)
    with pytest.raises(ValueError):mapping('unknown')
    with pytest.raises(ValueError):import_csv(dict(config,granularity='biflow'),tmp_path/'bad.csv')
    wrong=json.loads(json.dumps(config));wrong['files'][0]['sha256']='0'*64
    with pytest.raises(ValueError):import_csv(wrong,tmp_path/'bad.csv')
    wrong=dict(config,files=[config['files'][0],config['files'][0]])
    with pytest.raises(ValueError):import_csv(wrong,tmp_path/'bad.csv')
    with pytest.raises(ValueError):packet_frame(f.drop(columns=['tcp.len']))
    data.write_text(data.read_text()+'\n')
    with pytest.raises(ValueError):read_prepared(data,manifest)


def test_group_split_determinism_capture_session_and_duplicate_guards(tmp_path):
    data,manifest,_=fixture(tmp_path);f,_=read_prepared(data,manifest)
    a=prepare_split(f,75,3,1);b=prepare_split(f,75,3,1);assert a==b
    groups=[set(f.iloc[p].capture_id) for p in a['indices']]
    assert all(not groups[i]&groups[j] for i,j in [(0,1),(1,2),(0,2)])
    broken=f.copy();broken['capture_id']='one-normal-capture'
    with pytest.raises(ValueError,match='Insufficient independent'):prepare_split(broken,75,3,1)
    duplicated=f.copy();duplicated[FEATURES]=f.iloc[0][FEATURES].to_numpy()
    with pytest.raises(ValueError,match='after duplicate'):prepare_split(duplicated,75,3,1)


def test_schema_nonfinite_types_and_missing_imputed_on_train_only(tmp_path):
    data,manifest,_=fixture(tmp_path);f,_=read_prepared(data,manifest)
    for bad in [float('inf'),-1,True,'invalid']:
        broken=f.copy();broken['tcp.len']=bad
        with pytest.raises(ValueError):packet_frame(broken)
    broken=f.copy();broken['tcp.flags']=1.5
    with pytest.raises(ValueError):packet_frame(broken)
    f.loc[0,'tcp.len']=np.nan
    model,timing=fit_candidate(f,list(range(100)),settings()['candidates'][0],75)
    assert model.named_steps['impute'].statistics_[1]==f.iloc[:100]['tcp.len'].median()
    statistics=model.named_steps['impute'].statistics_.copy()
    heldout=f.iloc[200:205].copy();heldout['tcp.len']=60000
    model.predict(heldout)
    assert np.array_equal(statistics,model.named_steps['impute'].statistics_)
    assert timing['fit_attack']==int((f.iloc[:100].label==1).sum()) and timing['fit_normal']==int((f.iloc[:100].label==0).sum())


def test_if_only_normal_training_scaling_variants(tmp_path):
    data,manifest,_=fixture(tmp_path);f,_=read_prepared(data,manifest)
    for scaling in ['none','standard','robust']:
        spec=dict(settings()['candidates'][1],scaling=scaling)
        model,timing=fit_candidate(f,list(range(len(f))),spec,75)
        assert timing['fit_attack']==0 and timing['fit_rows']==180
        assert model.named_steps['impute'].statistics_[0]==f.loc[f.label==0,'frame.len'].median()
        assert model.named_steps['model'].contamination=='auto'


def test_operating_point_empty_class_scores_and_group_uncertainty():
    point=operating_point([0,0,1,1],[1,1,.1,.9],.05)
    assert point['threshold']>1 and point['status']=='no_detection_operating_point'
    metrics=binary_metrics([0,0],[.1,.2],.5)
    assert metrics['recall'] is None and metrics['roc_auc'] is None
    metrics=binary_metrics([0,1],[.1,.9],.5,['Normal','Flood'],['Normal','DoS'])
    assert metrics['per_attack_recall']['Flood']['seen_in_training'] is False
    for bad in [[np.nan,.1],[np.inf,.1],[-1,.1],[1.1,.1]]:
        with pytest.raises(ValueError):operating_point([0,1],bad)
    ci=cluster_intervals([0,1]*5,[0,1]*5,np.arange(10),repetitions=50)
    assert ci==cluster_intervals([0,1]*5,[0,1]*5,np.arange(10),repetitions=50)
    assert ci['zero_false_positive_capture_probability_upper_95']>0


def test_freeze_artifacts_once_only_test_and_offline_inference(tmp_path):
    data,manifest,_=fixture(tmp_path);config=settings();p=tmp_path/'plan.json'
    plan(data,manifest,config,p)
    frozen=train(data,manifest,p,tmp_path/'models',tmp_path/'experiment')
    assert frozen['test_evaluated'] is False and len(frozen['models'])==3
    assert all(row['timing']['fit_attack']==0 for row in frozen['models'] if row['algorithm']=='if')
    frozen_path=tmp_path/'experiment'/'freeze.json'
    altered=json.loads(frozen_path.read_text());altered['models'][0]['threshold']['threshold']+=.1;frozen_path.write_text(json.dumps(altered))
    with pytest.raises(ValueError,match='freeze'):final_test(data,manifest,p,tmp_path/'models',tmp_path/'experiment')
    frozen_path.write_text(json.dumps(frozen))
    result=final_test(data,manifest,p,tmp_path/'models',tmp_path/'experiment')
    assert result['scientific_quality_available'] is False
    row=frozen['models'][0];m,pipe=load(tmp_path/'models',row['model_id'],row['model_version'])
    assert m['mode']=='DEMO' and m['trusted_detector'] is False
    f,_=read_prepared(data,manifest)
    output=predict(m,pipe,f.iloc[:2],VERSION,'packet')
    assert all(x['trusted_detector'] is False and x['binding']=='unattributed' for x in output)
    with pytest.raises(ValueError):predict(m,pipe,f.iloc[:2],VERSION,'biflow')
    from src.classifier.research.external import evaluate_external
    with pytest.raises(ValueError,match='independent external'):evaluate_external(data,manifest,tmp_path/'models',tmp_path/'experiment',tmp_path/'external.json')
    with pytest.raises(FileExistsError):final_test(data,manifest,p,tmp_path/'models',tmp_path/'experiment')
    with pytest.raises(FileExistsError):train(data,manifest,p,tmp_path/'models',tmp_path/'experiment')
    artifact=tmp_path/'models'/row['model_id']/row['model_version']/'model.joblib'
    artifact.write_bytes(artifact.read_bytes()+b'tamper')
    with pytest.raises(ValueError,match='integrity'):load(tmp_path/'models',row['model_id'],row['model_version'])


def test_modified_plan_rejected_and_candidate_resource_limits(tmp_path):
    data,manifest,_=fixture(tmp_path);p=tmp_path/'plan.json';plan(data,manifest,settings(),p)
    value=json.loads(p.read_text());value['config']['seed']=1;p.write_text(json.dumps(value))
    with pytest.raises(ValueError,match='modified'):train(data,manifest,p,tmp_path/'models',tmp_path/'experiment')
    bad=settings();bad['candidates'][0]['parameters']['n_estimators']=100000
    with pytest.raises(ValueError):config_checked(bad)


def test_new_network_model_is_forbidden_in_online_telemetry_worker():
    from src.classifier.ml.worker import evaluate_one
    with pytest.raises(ValueError,match='Online network'):evaluate_one(None,None,{'task':'network_ids'},None)


def test_unknown_multiclass_attack_is_reported_not_invented(tmp_path):
    data,manifest,_=fixture(tmp_path);f,m=read_prepared(data,manifest)
    split=prepare_split(f,75,3,1)
    test_capture=f.iloc[split['indices'][2]].loc[lambda x:x.label==1].capture_id.iloc[0]
    f.loc[f.capture_id==test_capture,'attack_type']='Flood'
    f.to_csv(data,index=False);m['sha256']=file_hash(data);m['class_counts']={k:int(v) for k,v in f.attack_type.value_counts().items()}
    manifest.write_text(json.dumps(m))
    p=tmp_path/'plan.json';plan(data,manifest,settings(),p)
    train(data,manifest,p,tmp_path/'models',tmp_path/'exp')
    output=final_test(data,manifest,p,tmp_path/'models',tmp_path/'exp')
    multi=next(r for r in output['results'] if 'multiclass' in r['model_id'])
    assert multi['metrics']['multiclass']['unseen_test_categories']==['Flood']
    assert multi['metrics']['per_attack_recall']['Flood']['seen_in_training'] is False
    forest=next(r for r in output['results'] if 'if_test' in r['model_id'])
    assert all(v['seen_in_training'] is False for v in forest['metrics']['per_attack_recall'].values())


def test_flow_manifest_and_policy_schema_are_closed(tmp_path):
    data,manifest,_=fixture(tmp_path);m=json.loads(manifest.read_text());m['granularity']='unidirectional_flow';manifest.write_text(json.dumps(m))
    with pytest.raises(ValueError,match='granularity'):read_prepared(data,manifest)
    from src.policy.simulation import event
    from src.policy.signals import validate_ml
    from src.policy.profiles import registry
    raw=dict(event(1,'anomaly','ml',anomaly=True).original,feature_version=VERSION)
    with pytest.raises(ValueError,match='feature schema'):validate_ml(raw)
    assert [r['algorithm'] for r in registry()]==['Ascon-AEAD128']


def test_audited_packet_labels_preserve_normal_background(tmp_path):
    data,manifest,config=fixture(tmp_path)
    file=dict(config['files'][1]);path=Path(file['path']);raw=pd.read_csv(path)
    raw['is_attack']=[0,1]*6;raw.to_csv(path,index=False);file['sha256']=file_hash(path);file['label_column']='is_attack'
    audited=dict(config,files=[file],label_scope='packet_audited',synthetic=True)
    out=tmp_path/'audited.csv';m=import_csv(audited,out)
    assert m['class_counts']=={'Normal':6,'DoS':6}
    with pytest.raises(ValueError,match='label column'):import_csv(dict(audited,files=[dict(file,label_column='missing')]),tmp_path/'bad.csv')
    assert m['class_ontology']==sorted(['Normal','Bruteforce','DoS','Malformed','SlowITe','Flood'])


def test_balancing_is_train_only_and_provenance_cannot_be_predictive(tmp_path):
    data,manifest,_=fixture(tmp_path);f,_=read_prepared(data,manifest)
    indices=list(range(100))
    for weight in [None,'balanced','balanced_subsample']:
        spec=dict(settings()['candidates'][0],parameters=dict(n_estimators=4,class_weight=weight))
        model,stats=fit_candidate(f,indices,spec,75)
        assert model.named_steps['model'].class_weight==weight and stats['fit_rows']==100
        altered=f.iloc[200:210].copy()
        before=model.predict_proba(altered)
        altered['label']=1-altered.label;altered['attack_type']='LABEL_PROXY';altered['capture_id']='arbitrary-capture'
        np.testing.assert_array_equal(before,model.predict_proba(altered))

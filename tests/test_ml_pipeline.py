import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from src.classifier.ml.schema import network_frame,NETWORK_NUMERIC
from src.classifier.ml.network import build_network
from src.classifier.ml.telemetry_features import causal_frame,one_window,build_telemetry,UnknownDevice
from src.classifier.ml.splitting import split_frame
from src.classifier.ml.metrics import classification_metrics
from src.classifier.ml.train import train,evaluate
from src.classifier.ml.artifacts import load,verify
from src.classifier.ml.inference import network_inference
from ml_fixtures import telemetry_rows,network_rows,config


def test_network_schema_missing_bad_nan_unknown_and_train_only():
    data=network_rows()
    with pytest.raises(ValueError,match='Missing'): network_frame(data.drop(columns=['tcp.len']))
    bad=data.copy();bad.loc[0,'tcp.len']=np.inf
    with pytest.raises(ValueError): network_frame(bad)
    bad=data.copy();bad['tcp.len']='not-a-number'
    with pytest.raises(ValueError): network_frame(bad)
    data.loc[0,'tcp.len']=np.nan
    model=build_network('rf_binary',trees=8)
    model.fit(data.iloc[:120],data.Attack_label.iloc[:120])
    original=model.named_steps['prepare'].named_transformers_['numeric'].named_steps['impute'].statistics_.copy()
    holdout=data.iloc[120:].copy();holdout['http.request.method']='UNKNOWN_METHOD';holdout['tcp.len']=65534
    assert len(model.predict(holdout))==120
    np.testing.assert_array_equal(original,model.named_steps['prepare'].named_transformers_['numeric'].named_steps['impute'].statistics_)
    a=model.named_steps['prepare'].transform(model.named_steps['schema'].transform(data.iloc[[1]]))
    b=model[:-1].transform(data.iloc[[1]])
    np.testing.assert_array_equal(a,b)


def test_group_split_no_overlap_and_missing_group_rejected():
    data=network_rows();parts,report=split_frame(data,config('network_ids','rf_binary'))
    groups=[set(data.loc[p].capture_id) for p in parts]
    assert not groups[0]&groups[1] and not groups[0]&groups[2] and not groups[1]&groups[2]
    assert sum(report['counts'].values())==len(data)
    with pytest.raises(ValueError,match='group metadata'): split_frame(data.drop(columns='capture_id'),config('network_ids','rf_binary'))


def test_windows_causal_and_device_isolated():
    records=telemetry_rows(count=25)
    features,statuses=causal_frame(records,5)
    assert len(features)==60 and sum(s['status']=='warmup' for s in statuses)==15
    changed=[dict(row) for row in records]
    changed[-1]['temperature']=140
    other,_=causal_frame(changed,5)
    before=features['sequence_number']<25
    pd.testing.assert_frame_equal(features.loc[before],other.loc[before])
    target=records[18]  # raspb1 seq7
    mixed=[r for r in records[:18] if r['device_id']=='alpha'][-5:]
    with pytest.raises(ValueError,match='Mixed'): one_window(target,mixed,5)
    late=dict(target,measured_at=records[0]['measured_at'])
    prior=[r for r in records[:18] if r['device_id']=='raspb1'][-5:]
    assert one_window(late,prior,5)[1]=='out_of_order'
    model=build_telemetry();model.fit(features.iloc[:30])
    unknown=features.iloc[[0]].copy();unknown['device_id']='unseen'
    with pytest.raises(UnknownDevice): model.score_samples(unknown)


@pytest.mark.parametrize('task,algorithm',[('network_ids','rf_binary'),('network_ids','rf_multiclass'),
    ('network_ids','isolation_forest'),('telemetry_anomaly','statistical'),('telemetry_anomaly','isolation_forest')])
def test_training_export_reload_and_evaluation(tmp_path,task,algorithm):
    path=tmp_path/'synthetic.csv'
    data=network_rows() if task=='network_ids' else pd.DataFrame(telemetry_rows())
    data.to_csv(path,index=False)
    settings=config(task,algorithm)
    manifest=train(path,settings,tmp_path/'models')
    assert manifest['dataset']['synthetic'] is True
    assert manifest['dataset']['rows']==len(data)
    assert manifest['split']['counts']['test']>0
    assert manifest['preprocessing']['fit_rows']>0
    first,pipeline=load(tmp_path/'models','test-model','1.0.0')
    second,again=load(tmp_path/'models','test-model','1.0.0')
    assert first==second==manifest
    if task=='network_ids':
        a=network_inference(first,pipeline,data.iloc[:3],'network-core-v1')
        b=network_inference(second,again,data.iloc[:3],'network-core-v1')
        assert a==b
        with pytest.raises(ValueError):network_inference(first,pipeline,data.iloc[:1],'unsupported')
    else:
        features,_=causal_frame(data.to_dict('records'),settings['window'])
        np.testing.assert_array_equal(pipeline.score_samples(features),again.score_samples(features))
        assert manifest['metrics']['labelled_quality_available'] is False
    config_file=tmp_path/'evaluation.json';config_file.write_text(json.dumps(settings))
    with pytest.raises(ValueError,match='separate dataset'): evaluate(path,config_file,tmp_path/'models','test-model','1.0.0')
    artifact=tmp_path/'models'/'test-model'/'1.0.0'/'model.joblib'
    with artifact.open('ab') as stream:stream.write(b'CORRUPTED')
    with pytest.raises(ValueError,match='integrity'): load(tmp_path/'models','test-model','1.0.0')


def test_artifact_rejects_unknown_schema_dependencies_and_symlink(tmp_path):
    data=tmp_path/'synthetic.csv';pd.DataFrame(telemetry_rows()).to_csv(data,index=False)
    train(data,config(),tmp_path/'models')
    path=tmp_path/'models'/'test-model'/'1.0.0'/'manifest.json'
    original=path.read_text();manifest=json.loads(original)
    manifest['feature_version']='unknown';path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='feature'):verify(tmp_path/'models','test-model','1.0.0')
    manifest=json.loads(original);manifest['versions']['numpy']='impossible';path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='version'):verify(tmp_path/'models','test-model','1.0.0')
    path.write_text(original)
    alias=tmp_path/'alias';alias.symlink_to(tmp_path/'models',target_is_directory=True)
    with pytest.raises(ValueError,match='Symlink'):verify(alias,'test-model','1.0.0')


def test_no_dataset_substitution(tmp_path):
    with pytest.raises(ValueError,match='missing'):train(tmp_path/'missing.csv',config(),tmp_path/'models')


def test_metrics_need_ground_truth_classes():
    report=classification_metrics([0,0],[0,1],[0.1,0.8])
    assert report['false_positive_rate']==0.5
    assert report['roc_auc'] is None and report['pr_auc'] is None
    assert report['confusion_matrix']==[[1,1],[0,0]]

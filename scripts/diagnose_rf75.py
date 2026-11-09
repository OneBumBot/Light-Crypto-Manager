"""Read-only diagnosis of frozen stage6 artifacts; never fit or change any threshold."""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
from src.classifier.ml.artifacts import load,file_hash
from src.classifier.ml.network import risk_scores
from src.classifier.ml.schema import network_frame


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data',type=Path,required=True);p.add_argument('--models',required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();frame=pd.read_csv(args.data,low_memory=False)
    out=dict(mode='HISTORICAL_DIAGNOSIS_ONLY',fit_performed=False,threshold_changed=False,used_for_new_selection=False,runs=[])
    for mid in ['edge-network-rf-binary','edge-network-rf_multiclass','edge-network-isolation_forest']:
        # IDs are explicit caller-owned artifacts, never arbitrary internet pickle.
        try:m,pipeline=load(args.models,mid,'1.0.0')
        except FileNotFoundError:
            matches=[x.parent.parent.name for x in Path(args.models).glob('*/1.0.0/manifest.json') if json.loads(x.read_text())['algorithm']==({'edge-network-rf-binary':'rf_binary','edge-network-rf_multiclass':'rf_multiclass','edge-network-isolation_forest':'isolation_forest'}[mid])]
            if len(matches)!=1:raise ValueError('Ambiguous frozen baseline artifact')
            mid=matches[0];m,pipeline=load(args.models,mid,'1.0.0')
        if file_hash(args.data)!=m['dataset']['sha256']:raise ValueError('Baseline dataset hash mismatch')
        item=dict(model_id=mid,artifact_sha256=m['artifact_sha256'],dataset_sha256=m['dataset']['sha256'],threshold=m['threshold'],partitions={})
        sets=[]
        for name,indices in zip(['train','validation','test'],m['split']['indices']):
            sub=frame.iloc[indices];scores=risk_scores(pipeline,sub,m['algorithm']);binary=sub.Attack_label.to_numpy()
            groups=set(sub.flow_group);sets.append(groups)
            item['partitions'][name]=dict(rows=len(sub),groups=len(groups),classes={k:int(v) for k,v in sub.Attack_type.value_counts().items()},
                probability_or_score_quantiles={str(label):np.quantile(scores[binary==label],[0,.05,.5,.95,1]).tolist() if (binary==label).any() else None for label in [0,1]},
                scores_at_one=int((scores==1).sum()),scores_above_threshold=int((scores>=m['threshold']).sum()),
                constant_features=sorted([c for c,v in network_frame(sub).nunique(dropna=False).items() if v<=1]))
        item['cross_partition_groups']=len((sets[0]&sets[1])|(sets[0]&sets[2])|(sets[1]&sets[2]))
        val=item['partitions']['validation'];n=val['classes'].get('Normal',0)
        item['validation_normal_count']=n;item['max_false_positives_at_empirical_5_percent']=int(n*.05)
        item['training_categories']=sorted(item['partitions']['train']['classes'])
        item['unseen_test_categories']=sorted(set(item['partitions']['test']['classes'])-set(item['training_categories']))
        if hasattr(pipeline.named_steps['model'],'feature_importances_'):
            cols=pipeline.named_steps['prepare'].get_feature_names_out();importance=pipeline.named_steps['model'].feature_importances_
            item['frozen_model_top_importances']=[dict(feature=str(cols[i]),importance=float(importance[i])) for i in np.argsort(importance)[-10:][::-1]]
        out['runs'].append(item)
    with args.output.open('x') as stream:json.dump(out,stream,indent=2,allow_nan=False)
    print('Frozen baseline diagnosis saved; no training, selection or threshold changes')

if __name__=='__main__':main()

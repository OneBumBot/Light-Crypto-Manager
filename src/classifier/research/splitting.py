"""Frozen capture-level partitions. Never falls back to packets or arbitrary time blocks."""
import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold
from .schema import packet_frame
from .datasets import canonical_hash


def prepare_split(frame,seed=75,min_normal_rows=1000,min_class_groups=5):
    if type(seed) is not int or type(min_normal_rows) is not int or min_normal_rows<1 or type(min_class_groups) is not int or min_class_groups<1:
        raise ValueError('Invalid split support settings')
    support={str(label):int(frame.loc[frame.label==label].capture_id.nunique()) for label in [0,1]}
    if any(support[str(label)]<3*min_class_groups for label in [0,1]):
        raise ValueError('Insufficient independent captures per class for train/validation/test: '+str(support))
    splitter=StratifiedGroupKFold(n_splits=5,shuffle=True,random_state=seed)
    folds=list(splitter.split(frame,frame.label,frame.capture_id))
    test=np.asarray(folds[0][1]);validation=np.asarray(folds[1][1]);train=np.setdiff1d(np.arange(len(frame)),np.r_[test,validation])
    parts=[train,validation,test]
    before_summary={name:{'rows':len(p),'classes':{k:int(v) for k,v in frame.iloc[p].attack_type.value_counts().items()}}
                    for name,p in zip(['train','validation','test'],parts)}
    # Conservative exact predictive-feature guard. Report its distribution-changing cost.
    fingerprints=pd.util.hash_pandas_object(packet_frame(frame),index=False)
    sets=[set(fingerprints.iloc[p]) for p in parts]
    crossing=(sets[0]&sets[1])|(sets[0]&sets[2])|(sets[1]&sets[2])
    removed=[]
    for n,p in enumerate(parts):
        parts[n]=p[~fingerprints.iloc[p].isin(crossing).to_numpy()]
        removed.append(int(len(p)-len(parts[n])))
    summary={}
    for name,p in zip(['train','validation','test'],parts):
        sub=frame.iloc[p]
        normal=int((sub.label==0).sum());attack=int((sub.label==1).sum())
        groups={str(label):int(sub.loc[sub.label==label].capture_id.nunique()) for label in [0,1]}
        if normal<min_normal_rows or attack<1 or min(groups.values())<min_class_groups:
            raise ValueError('Insufficient class/support after duplicate isolation in '+name)
        summary[name]=dict(rows=len(p),normal=normal,attack=attack,captures=int(sub.capture_id.nunique()),
            class_groups=groups,attack_types={k:int(v) for k,v in sub.attack_type.value_counts().items()})
    groups=[set(frame.iloc[p].capture_id) for p in parts]
    if any(groups[a]&groups[b] for a,b in [(0,1),(0,2),(1,2)]):raise ValueError('Capture leakage')
    sessions=[set(frame.iloc[p].session_id) for p in parts]
    if any(sessions[a]&sessions[b] for a,b in [(0,1),(0,2),(1,2)]):raise ValueError('Session leakage')
    result=dict(schema_version=1,method='stratified_capture_5fold_60_20_20',seed=seed,
        minimum_normal_rows=min_normal_rows,minimum_class_captures=min_class_groups,
        indices=[p.tolist() for p in parts],summary=summary,before_duplicate_purge=before_summary,duplicate_purged_rows=removed,
        duplicate_policy='all exact predictive fingerprints crossing partitions removed; may alter prevalence',
        independent_devices_verified=False)
    result['sha256']=canonical_hash(result)
    return result

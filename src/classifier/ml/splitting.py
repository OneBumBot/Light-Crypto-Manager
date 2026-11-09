"""No row-random fallback. Split metadata is kept outside predictive features."""
import hashlib
import numpy as np
import pandas as pd


def split_frame(frame, config):
    seed=config['random_state']
    strategy=config['split_strategy']
    fractions=config.get('fractions',[0.6,0.2,0.2])
    if len(fractions)!=3 or min(fractions)<=0 or not np.isclose(sum(fractions),1):
        raise ValueError('Three positive split fractions must sum to one')
    if strategy=='group':
        column=config.get('group_column')
        if not column or column not in frame or frame[column].isna().any():
            raise ValueError('Reliable group metadata required; no random-row fallback')
        groups=sorted(frame[column].astype(str).unique())
        if len(groups)<5: raise ValueError('At least five independent groups required')
        if config.get('stratify_group_labels'):
            from sklearn.model_selection import StratifiedGroupKFold
            if fractions!=[0.6,0.2,0.2] or config['stratify_group_labels'] not in frame:
                raise ValueError('Grouped stratification requires 60/20/20 and explicit labels')
            splitter=StratifiedGroupKFold(n_splits=5,shuffle=True,random_state=seed)
            folds=list(splitter.split(frame,frame[config['stratify_group_labels']],frame[column].astype(str)))
            test=frame.index[folds[0][1]].to_numpy();validation=frame.index[folds[1][1]].to_numpy()
            train=frame.index[~frame.index.isin(np.r_[test,validation])].to_numpy()
            parts=[train,validation,test]
            if any(len(p)==0 for p in parts): raise ValueError('Empty grouped stratified split')
            return parts,{'strategy':'stratified_group_5fold_60_20_20',
                'counts':dict(zip(['train','validation','test'],map(len,parts))),'excluded_rows':0,
                'indices_sha256':[hashlib.sha256(','.join(map(str,p)).encode()).hexdigest() for p in parts],
                'indices':[list(map(int,p)) for p in parts]}
        rng=np.random.default_rng(seed); rng.shuffle(groups)
        a=max(1,int(len(groups)*fractions[0])); b=max(a+1,int(len(groups)*sum(fractions[:2])))
        b=min(b,len(groups)-1)
        parts=[frame.index[frame[column].astype(str).isin(g)].to_numpy() for g in [groups[:a],groups[a:b],groups[b:]]]
    elif strategy=='time':
        column=config.get('time_column')
        if not column or column not in frame: raise ValueError('Time split requires explicit timestamp column')
        timestamps=pd.to_datetime(frame[column],utc=True,errors='raise',format=config.get('time_format','ISO8601'))
        if timestamps.isna().any(): raise ValueError('Missing split timestamps')
        unique=np.sort(timestamps.unique())
        if len(unique)<5: raise ValueError('Insufficient distinct split times')
        a=min(max(1,int(len(unique)*fractions[0])),len(unique)-2)
        b=min(max(a+1,int(len(unique)*sum(fractions[:2]))),len(unique)-1)
        gap=pd.Timedelta(config.get('purge_seconds',0),unit='s')
        if gap<pd.Timedelta(0): raise ValueError('Negative purge interval')
        masks=[timestamps<unique[a]-gap,(timestamps>=unique[a]) & (timestamps<unique[b]-gap),timestamps>=unique[b]]
        group=config.get('group_column')
        if group:
            if group not in frame or frame[group].isna().any(): raise ValueError('Invalid temporal group metadata')
            sets=[set(frame.loc[mask,group].astype(str)) for mask in masks]
            crossing=(sets[0]&sets[1]) | (sets[0]&sets[2]) | (sets[1]&sets[2])
            masks=[mask & ~frame[group].astype(str).isin(crossing) for mask in masks]
        parts=[frame.index[mask].to_numpy() for mask in masks]
    else:
        raise ValueError('Only group or time splitting is supported')
    if any(len(p)==0 for p in parts): raise ValueError('Empty split after grouping/purge')
    return parts, {'strategy':strategy,'counts':dict(zip(['train','validation','test'],map(len,parts))),
        'excluded_rows':len(frame)-sum(map(len,parts)),
        'indices_sha256':[hashlib.sha256(','.join(map(str,p)).encode()).hexdigest() for p in parts],
        'indices':[list(map(int,p)) for p in parts]}

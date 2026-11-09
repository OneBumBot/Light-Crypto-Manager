"""Validation operating point, explicit task scopes and capture-cluster uncertainty."""
import numpy as np
from sklearn.metrics import precision_recall_fscore_support,confusion_matrix,roc_auc_score,average_precision_score,precision_recall_curve,auc


def scores_checked(scores):
    values=np.asarray(scores,dtype=float)
    if values.ndim!=1 or not len(values) or not np.isfinite(values).all() or (values<0).any() or (values>1).any():
        raise ValueError('Finite nonempty model-specific score in [0,1] required')
    return values


def operating_point(truth,scores,target=.05):
    score=scores_checked(scores);truth=np.asarray(truth)
    if len(truth)!=len(score) or set(truth.tolist())!={0,1} or not 0<target<1:raise ValueError('Both validation classes and valid target required')
    order=np.argsort(-score,kind='stable');s=score[order];y=truth[order]
    ends=np.r_[np.flatnonzero(s[:-1]!=s[1:]),len(s)-1]
    tp=np.cumsum(y)[ends];fp=np.cumsum(1-y)[ends];normal=int((y==0).sum());positive=int(y.sum())
    fpr=fp/normal;f1=2*tp/np.maximum(1,tp+fp+positive)
    eligible=np.flatnonzero(fpr<=target)
    if not len(eligible):threshold=float(np.nextafter(score.max(),np.inf));quality=0.0
    else:
        best=max(eligible,key=lambda i:(f1[i],-fpr[i],s[ends[i]]))
        threshold=float(s[ends[best]]);quality=float(f1[best])
        if quality==0:threshold=float(np.nextafter(score.max(),np.inf))
    return dict(threshold=threshold,method='validation-only attack F1 under empirical normal FPR constraint; no test tuning',
        empirical_fpr_target=target,validation_normal=normal,validation_attack=positive,
        status='no_detection_operating_point' if threshold>score.max() else 'selected',validation_attack_f1=quality)


def binary_metrics(truth,scores,threshold,attack_types=None,train_types=()):
    score=scores_checked(scores);y=np.asarray(truth)
    if len(y)!=len(score) or not set(y.tolist())<={0,1} or type(threshold) not in (int,float) or not np.isfinite(threshold):raise ValueError('Invalid evaluation targets/threshold')
    pred=(score>=threshold).astype(int);p,r,f,_=precision_recall_fscore_support(y,pred,labels=[0,1],zero_division=0)
    normal=y==0;positive=y==1
    result=dict(objects=len(y),confusion_matrix=confusion_matrix(y,pred,labels=[0,1]).tolist(),labels=[0,1],
        precision=float(p[1]),recall=float(r[1]) if positive.any() else None,f1=float(f[1]),macro_f1=float(f.mean()),
        balanced_accuracy=float((r[0]+r[1])/2) if normal.any() and positive.any() else None,
        fpr=float(pred[normal].mean()) if normal.any() else None,pr_auc=None,roc_auc=None,
        score_semantics='RF 1-P(normal) or IF -score_samples; not a calibrated attack probability',per_attack_recall={})
    if normal.any() and positive.any():
        precision,recall,_=precision_recall_curve(y,score)
        result.update(pr_auc=float(auc(recall,precision)),average_precision=float(average_precision_score(y,score)),roc_auc=float(roc_auc_score(y,score)))
    else:result['auc_unavailable_reason']='One binary class absent'
    if attack_types is not None:
        types=np.asarray(attack_types)
        for name in sorted(set(types[positive])):
            mask=types==name;result['per_attack_recall'][str(name)]=dict(objects=int(mask.sum()),recall=float(pred[mask].mean()),seen_in_training=name in train_types)
    return result


def cluster_intervals(truth,prediction,groups,seed=75,repetitions=200):
    y=np.asarray(truth);pred=np.asarray(prediction);groups=np.asarray(groups);unique=np.unique(groups)
    if len(unique)<5:return {'available':False,'reason':'Fewer than five independent capture groups'}
    # Aggregate confusion contributions before resampling groups, not individual packets.
    counts=[]
    for g in unique:
        mask=groups==g;counts.append([np.sum(mask&(y==1)&(pred==1)),np.sum(mask&(y==0)&(pred==1)),np.sum(mask&(y==0)),np.sum(mask&(y==1))])
    counts=np.asarray(counts);rng=np.random.default_rng(seed);samples={k:[] for k in ['precision','recall','fpr']}
    for _ in range(repetitions):
        tp,fp,normal,attack=counts[rng.integers(0,len(unique),len(unique))].sum(axis=0)
        for key,num,den in [('precision',tp,tp+fp),('recall',tp,attack),('fpr',fp,normal)]:
            if den:samples[key].append(float(num/den))
    normal_groups=int((counts[:,2]>0).sum())
    return dict(available=True,method='capture cluster percentile bootstrap,95%; assumes captures independent',groups=len(unique),
        repetitions=repetitions,intervals={k:np.quantile(v,[.025,.975]).tolist() if v else None for k,v in samples.items()},
        zero_false_positive_capture_probability_upper_95=(float(1-.05**(1/normal_groups)) if normal_groups and counts[:,1].sum()==0 else None),
        limitation='Zero-event bootstrap can be [0,0]; it does not prove zero population FPR. Extra upper bound concerns probability of any FP in a capture, not packet FPR.')

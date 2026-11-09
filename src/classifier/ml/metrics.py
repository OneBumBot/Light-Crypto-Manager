"""Label-based metrics only. Unlabelled telemetry never supplies pseudo ground truth."""
import numpy as np
from sklearn.metrics import (classification_report,confusion_matrix,f1_score,
    precision_recall_curve,auc,roc_auc_score,average_precision_score)


def classification_metrics(truth,prediction,score,normal=0):
    truth=np.asarray(truth); prediction=np.asarray(prediction)
    labels=sorted(set(truth.tolist()) | set(prediction.tolist()),key=str)
    binary=(truth!=normal).astype(int); predicted_binary=(prediction!=normal).astype(int)
    negatives=binary==0
    result={'objects':len(truth),'labels':[str(x) for x in labels],
        'classification_report':classification_report(truth,prediction,labels=labels,output_dict=True,zero_division=0),
        'macro_f1':float(f1_score(truth,prediction,labels=labels,average='macro',zero_division=0)),
        'confusion_matrix':confusion_matrix(truth,prediction,labels=labels).tolist(),
        'false_positive_rate':float(predicted_binary[negatives].mean()) if negatives.any() else None,
        'roc_auc':None,'pr_auc':None,'average_precision':None,
        'auc_scope':'binary attack-vs-normal risk, including for multiclass classifiers'}
    if len(set(binary))==2:
        precision,recall,_=precision_recall_curve(binary,score)
        result.update(roc_auc=float(roc_auc_score(binary,score)),pr_auc=float(auc(recall,precision)),
                      average_precision=float(average_precision_score(binary,score)))
    else: result['auc_unavailable_reason']='both normal and attack labels are required'
    return result


def choose_threshold(truth,scores,max_fpr=0.05):
    truth=np.asarray(truth,dtype=int); scores=np.asarray(scores,dtype=float)
    if not 0<max_fpr<1 or not (truth==0).any(): raise ValueError('Normal validation and valid FPR target required')
    candidates=np.unique(np.r_[scores,np.nextafter(scores.max(),np.inf)])
    if len(candidates)>256: candidates=np.quantile(candidates,np.linspace(0,1,256))
    best=None
    for threshold in candidates:
        prediction=(scores>=threshold).astype(int)
        fpr=prediction[truth==0].mean()
        if fpr>max_fpr: continue
        quality=f1_score(truth,prediction,zero_division=0)
        item=(float(quality),-float(fpr),float(threshold))
        if best is None or item>best: best=item
    return best[2] if best else float(np.nextafter(scores.max(),np.inf))

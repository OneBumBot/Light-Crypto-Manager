"""Validation-only session aggregation and known-subset cluster evaluation."""
import numpy as np
import pandas as pd
from .metrics import scores_checked,operating_point,binary_metrics,cluster_intervals
SCENARIOS=['regular','jitter','qos1_retry','bad_credentials','forbidden_acl','replay','tampered','bounded_rate','pattern_change']


def sessions(frame,scores,method,packet_threshold):
 if method not in ['mean','max','fraction']:raise ValueError('Unknown preregistered session aggregator')
 values=frame.copy();values['_score']=scores_checked(scores)
 result=[]
 for identity,sub in values.groupby('session_id',sort=False):
  if sub.label.nunique()!=1 or sub.independence_group.nunique()!=1:raise ValueError('Ambiguous session target/group')
  score=float(sub._score.mean()) if method=='mean' else float(sub._score.max()) if method=='max' else float(sub._score.ge(packet_threshold).mean())
  result.append(dict(session_id=identity,label=int(sub.label.iloc[0]),score=score,group=sub.independence_group.iloc[0],scenario=sub.scenario_category.iloc[0],rows=len(sub)))
 return pd.DataFrame(result)


def calibrate(frame,scores,packet_threshold,target):
 results=[]
 for method in ['mean','max','fraction']:
  values=sessions(frame,scores,method,packet_threshold);point=operating_point(values.label,values.score.to_numpy(),target);metrics=binary_metrics(values.label,values.score.to_numpy(),point['threshold'])
  results.append(dict(method=method,point=point,validation=metrics,score_distribution=distribution(values.score.to_numpy())))
 index=max(range(len(results)),key=lambda i:(results[i]['validation']['f1'],-results[i]['validation']['fpr'],-i))
 return dict(selected=results[index],candidates=results,selection_scope='validation only; labelled subset of corroborated sessions, not unknown packets',detection_time='not_measured_offline')


def distribution(scores):
 s=scores_checked(scores);counts,edges=np.histogram(s,bins=np.linspace(0,1,21))
 return dict(n=len(s),min=float(s.min()),max=float(s.max()),mean=float(s.mean()),quantiles=np.quantile(s,[0,.25,.5,.75,1]).tolist(),histogram_counts=counts.tolist(),histogram_edges=edges.tolist())


def cluster_metrics(labels,scores,threshold,groups,seed):
 value=cluster_intervals(labels,(scores_checked(scores)>=threshold).astype(int),groups,seed)
 if value.get('available'):
  value['method']='acquisition-block cluster percentile bootstrap,95%; assumes repeated blocks conditionally independent within one host'
  value['zero_false_positive_block_probability_upper_95']=value.pop('zero_false_positive_capture_probability_upper_95')
  value['limitation']='Only six held-out acquisition blocks; zero-event bootstrap may be degenerate; no packet IID or external-domain claim'
 return value


def evaluation(frame,scores,packet_threshold,session_calibration,seed):
 s=scores_checked(scores);selected=session_calibration['selected'];grouped=sessions(frame,s,selected['method'],packet_threshold);threshold=selected['point']['threshold'];session=binary_metrics(grouped.label,grouped.score.to_numpy(),threshold);session.update(session_detection_rate=session['recall'],false_alarms_per_normal_session=session['fpr'],score_semantics='Untrusted validation-calibrated aggregation; not attack probability');session['uncertainty']=cluster_metrics(grouped.label,grouped.score.to_numpy(),threshold,grouped.group,seed)
 per_scenario={}
 for name in SCENARIOS:
  mask=frame.scenario_category.eq(name).to_numpy();g=grouped.loc[grouped.scenario==name]
  if not mask.any():per_scenario[name]=dict(status='not_evaluable',reason='No verified retained observations in this holdout scenario',rows=0,metrics=None);continue
  per_scenario[name]=dict(status='evaluated_known_subset' if frame.loc[mask,'label'].nunique()==2 else 'controlled_violation_recall_not_evaluable',rows=int(mask.sum()),groups=int(frame.loc[mask,'independence_group'].nunique()),packet=binary_metrics(frame.loc[mask,'label'],s[mask],packet_threshold),session=binary_metrics(g.label,g.score.to_numpy(),threshold) if len(g) else None)
 captures={}
 for capture,sub in frame.assign(_score=s).groupby('capture_id'):
  captures[capture]=dict(rows=len(sub),positive_rows=int(sub.label.sum()),normal_rows=int(sub.label.eq(0).sum()),scope='retained known observations only; not complete-capture safety',metrics=binary_metrics(sub.label,sub._score.to_numpy(),packet_threshold))
 return dict(label_unit='connection_activity/window_behavior',session_aggregation=selected['method'],session_threshold=threshold,session=session,per_scenario=per_scenario,per_capture=captures,packet_cluster_uncertainty=cluster_metrics(frame.label,s,packet_threshold,frame.independence_group,seed),unknown_scope='Unknown observations excluded; no claim about uncorroborated sessions or packet-specific maliciousness',detection_time='not_measured_offline')

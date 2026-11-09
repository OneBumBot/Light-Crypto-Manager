"""Offline network input interface. Never emits a device-bound trusted policy signal."""
from .schema import VERSION,packet_frame
from .experiment import risk


def predict(manifest,pipeline,frame,feature_version,granularity):
    if manifest['task']!='network_ids' or feature_version!=VERSION or manifest['feature_version']!=VERSION or granularity!='packet':
        raise ValueError('Incompatible offline network observation contract')
    if manifest.get('trusted_detector') is not False or manifest['mode'] not in {'DEMO','RESEARCH'}:raise ValueError('Research trust invariant')
    packet_frame(frame)
    algorithm='if' if manifest['algorithm']=='isolation_forest' else 'rf'
    scores=risk(pipeline,frame,algorithm)
    types=pipeline.predict(frame).tolist() if manifest['algorithm']=='rf_multiclass' else [None]*len(scores)
    return [dict(contract_version='offline-network-risk-v1',detector='network_ids',granularity='packet',predicted_attack_type=label,model_id=manifest['model_id'],model_version=manifest['model_version'],feature_version=VERSION,
        score=float(score),threshold=manifest['threshold'],is_anomaly=bool(score>=manifest['threshold']),
        score_direction='higher_is_more_anomalous',score_range=[0,1],mode=manifest['mode'],trusted_detector=False,
        binding='unattributed',interpretation='Offline network anomaly/risk; no authenticated device mapping or attack confirmation') for score,label in zip(scores,types)]

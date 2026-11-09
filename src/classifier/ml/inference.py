"""Explicit interfaces: network collector input is never the telemetry payload."""
import numpy as np
from .schema import NETWORK_VERSION
from .network import risk_scores


def network_inference(manifest,pipeline,frame,feature_version):
    if manifest['task']!='network_ids' or feature_version!=NETWORK_VERSION or manifest['feature_version']!=feature_version:
        raise ValueError('Incompatible network collector contract')
    scores=risk_scores(pipeline,frame,manifest['algorithm'])
    if not np.isfinite(scores).all(): raise ValueError('Nonfinite model score')
    classes=pipeline.predict(frame).tolist() if manifest['algorithm']=='rf_multiclass' else (scores>=manifest['threshold']).astype(int).tolist()
    return [dict(detector='network_ids',model_id=manifest['model_id'],model_version=manifest['model_version'],
        feature_version=feature_version,score=float(score),threshold=manifest['threshold'],
        predicted_class=label,is_anomaly=bool(score>=manifest['threshold']),mode=manifest['mode'])
        for score,label in zip(scores,classes)]

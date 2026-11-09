"""Read-only signal contract for a future Policy Engine; never chooses encryption."""
from datetime import datetime
import math


def signal(event,model):
    if event['status']!='ok':raise ValueError('Only scored events have an anomaly signal')
    score=event['score'];threshold=event['threshold']
    if not all(type(v) in (float,int) and math.isfinite(v) and v>=0 for v in [score,threshold]):
        raise ValueError('Invalid signal scale')
    evaluated=event['evaluated_at']
    return dict(signal_version=1,device_id=event['device_id'],key_epoch=event['key_epoch'],
        sequence_number=event['sequence_number'],detector=event['detector'],model_id=event['model_id'],
        model_version=event['model_version'],feature_version=event['feature_version'],
        score=score,threshold=threshold,is_anomaly=event['is_anomaly'],
        evaluated_at=evaluated.isoformat() if isinstance(evaluated,datetime) else evaluated,
        score_direction='higher_is_more_anomalous',score_range=[0,model.get('score_upper_bound')],
        score_semantics=model.get('score_semantics'),mode=model['mode'],trusted_detector=False,
        interpretation='Anomaly signal, not confirmation of a cyberattack')

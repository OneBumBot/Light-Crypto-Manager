"""Fixed Stage13 golden traces; UTC evaluation time is explicit, no live ML."""
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from src.policy.signals import Signal
from src.policy.engine import State
from src.policy.rules import Rules
T=datetime(2026,1,1,tzinfo=timezone.utc)


def event(n,category='accepted',source='protocol',occurred=None):
    at=T+timedelta(seconds=n if occurred is None else occurred)
    return Signal('gold:'+str(n)+':'+category,source,category,at.isoformat(),(T+timedelta(seconds=n)).isoformat(),'alpha',1,n+1,'authenticated','monitor' if source in ['ml','system'] else 'verified')


def ml(n,status='ok',anomaly=False):
    raw=dict(signal_version=1,device_id='alpha',key_epoch=1,sequence_number=n+1,detector='telemetry_anomaly',model_id='public-research',model_version='v1',feature_version='telemetry-causal-v1',score=.9 if anomaly else .1,threshold=.5,is_anomaly=anomaly,evaluated_at=(T+timedelta(seconds=n)).isoformat(),score_direction='higher_is_more_anomalous',score_range=[0,1],score_semantics='research statistical anomaly score; not attack probability',mode='RESEARCH',trusted_detector=False,interpretation='Anomaly signal, not confirmation of a cyberattack',status=status)
    if status!='ok':raw.update(score=None,threshold=None,is_anomaly=None)
    return replace(event(n,'unavailable' if status!='ok' else 'anomaly' if anomaly else 'normal','ml'),original=raw)


def traces():
    normal=[event(0),ml(1),event(2)]
    replay=[event(n,'replay') for n in [1,2,3]]
    recovery=[event(1),ml(2),event(3),event(6),event(11),event(12)]
    small=Rules(cooldown_seconds=2,recovery_seconds=8,recovery_observations=3,min_decision_seconds=1)
    return [
      ('healthy-normal',State(),Rules(),normal),
      ('watch-alert-critical',State(),Rules(),replay+[event(4,'security_violation')]),
      ('alert-recovery',State(risk='ALERT',guard='ALERT',changed_at=T.isoformat()),small,recovery),
      ('critical-recovery',State(risk='CRITICAL',guard='CRITICAL',changed_at=T.isoformat()),small,recovery),
      ('missing-ml',State(),Rules(),[event(0),event(2)]),
      ('stale-ml-telemetry',State(),Rules(),normal+[event(140),ml(141,'unavailable')]),
      ('synthetic-stale',State(risk='ALERT',guard='ALERT'),Rules(),[event(1,'stale','system')]),
      ('physical-delay-not-attack',State(),Rules(),[event(1,'physical_anomaly','rule'),event(2,'delivery_delay','rule')]),
      ('late-future-duplicate',State(),Rules(),[event(10),event(11,occurred=5),event(12,occurred=400),event(10)]),
      ('unattributed',State(),Rules(),[Signal('gold:reject','protocol','rejected',T.isoformat(),T.isoformat())]),
      ('ml-research-anomaly',State(),Rules(),[event(0),ml(1,anomaly=True),ml(2,anomaly=False)]),
      ('ml-out-of-order',State(),Rules(),[event(0),ml(10),replace(ml(11),occurred_at=(T+timedelta(seconds=5)).isoformat(),original={**ml(11).original,'evaluated_at':(T+timedelta(seconds=5)).isoformat()})]),
    ]

"""Pure deterministic state machine with bounded evidence and injected UTC time."""
from dataclasses import dataclass, field, asdict
from datetime import timedelta
from .signals import utc
from .profiles import ASCON, recommend

STATES={'NORMAL','WATCH','ALERT','CRITICAL','UNKNOWN'}
LEVEL={'NORMAL':0,'WATCH':1,'ALERT':2,'CRITICAL':3}
ALLOWED={'UNKNOWN': {'NORMAL','WATCH','ALERT','CRITICAL'},
         'NORMAL': {'UNKNOWN','WATCH','ALERT','CRITICAL'},
         'WATCH': {'UNKNOWN','NORMAL','ALERT','CRITICAL'},
         'ALERT': {'UNKNOWN','NORMAL','WATCH','CRITICAL'},
         'CRITICAL': {'UNKNOWN','NORMAL'}}

@dataclass
class State:
    risk: str = 'UNKNOWN'
    guard: str = 'NORMAL'
    changed_at: str | None = None
    last_decision_at: str | None = None
    last_event_at: str | None = None
    last_telemetry_at: str | None = None
    last_ml_at: str | None = None
    ml_available: bool = False
    stable_since: str | None = None
    healthy_count: int = 0
    evidence: list = field(default_factory=list)
    healthy_evidence: list = field(default_factory=list)
    def payload(self):return asdict(self)


def evaluate(state,signal,rules,now,*,mode='DRY_RUN',capabilities=('mqtt_tls','aead','telemetry_v2')):
    signal.validate();rules.validate();now=utc(now)
    if mode not in {'DRY_RUN','SIMULATION'}:raise ValueError('Live application is unavailable')
    if state.risk not in STATES or state.guard not in LEVEL:raise ValueError('Invalid state')
    s=State(**state.payload());previous=s.risk
    occurred=utc(signal.occurred_at)
    reason=[];suppressed=False;diagnostic='accepted';used=[]
    age=(now-occurred).total_seconds()
    if age>rules.max_age_seconds or age < -rules.future_skew_seconds:
        diagnostic='stale' if age>0 else 'future';reason=[diagnostic]
    elif signal.binding=='unattributed' or signal.device_id is None:
        diagnostic='unattributed';reason=['No authenticated device binding']
    elif signal.binding=='simulation' and mode!='SIMULATION':
        diagnostic='rejected';reason=['Simulation provenance forbidden in runtime']
    elif s.last_event_at and occurred<utc(s.last_event_at):
        diagnostic='late';reason=['Late evidence retained for audit, not applied retroactively']
    else:
        s.last_event_at=occurred.isoformat();used=[signal.event_id]
        s.evidence=[e for e in s.evidence if utc(e['at'])>=now-timedelta(seconds=rules.window_seconds)][-127:]
        authenticated=(signal.trust=='verified' and signal.binding=='authenticated') or (mode=='SIMULATION' and signal.trust=='simulation')
        attack=authenticated and signal.source=='protocol' and signal.category in {'replay','security_violation'}
        critical=attack and signal.category=='security_violation'
        healthy=authenticated and signal.source=='protocol' and signal.category=='accepted'
        if signal.source=='system' and signal.category=='unavailable' and signal.original=={'component':'ml'}:
            s.ml_available=False
        if signal.source=='ml':
            s.last_ml_at=occurred.isoformat();s.ml_available=signal.category!='unavailable'
        if healthy:
            if s.last_telemetry_at and (occurred-utc(s.last_telemetry_at)).total_seconds()>rules.telemetry_fresh_seconds:
                s.stable_since=None;s.healthy_count=0;s.healthy_evidence=[]
            s.last_telemetry_at=occurred.isoformat()
            if s.stable_since is None:s.stable_since=occurred.isoformat();s.healthy_count=0;s.healthy_evidence=[]
            s.healthy_count=min(128,s.healthy_count+1)
            s.healthy_evidence=(s.healthy_evidence+[signal.event_id])[-128:]
        if attack:
            s.evidence.append({'event_id':signal.event_id,'at':occurred.isoformat()})
            s.stable_since=None;s.healthy_count=0;s.healthy_evidence=[]
        if signal.source=='rule' or (signal.source=='ml' and signal.category=='anomaly'):
            s.stable_since=None;s.healthy_count=0;s.healthy_evidence=[]
        count=len(s.evidence)
        target=s.risk
        if rules.strategy=='fixed':
            target='NORMAL' if healthy and s.guard=='NORMAL' and s.ml_available and s.last_ml_at and (now-utc(s.last_ml_at)).total_seconds()<=rules.ml_fresh_seconds else ('UNKNOWN' if healthy and not s.ml_available else s.risk)
            reason=['Fixed protection baseline; insufficient data still means UNKNOWN']
        elif critical:target='CRITICAL';reason=['Verified security rule violation']
        elif count>=rules.alert_observations:target='ALERT';reason=['Sustained authenticated replay evidence']
        elif count>=rules.watch_observations:target='WATCH';reason=['Repeated authenticated replay evidence']
        elif signal.source=='rule':target='WATCH' if LEVEL[s.guard]<1 else s.guard;reason=['Physical/delivery rule; not a confirmed cyberattack']
        elif mode=='SIMULATION' and rules.strategy=='adaptive_research' and signal.source=='ml' and signal.category=='anomaly':
            target='WATCH';reason=['SIMULATION: research recommendation only']
        elif signal.source in {'ml','system'} and signal.category in {'unavailable','stale'}:
            target='UNKNOWN';reason=['Insufficient information; protected configuration retained']
        elif healthy:
            if s.risk=='UNKNOWN' and s.guard=='NORMAL' and s.healthy_count>=2 and s.ml_available and s.last_ml_at and (now-utc(s.last_ml_at)).total_seconds()<=rules.ml_fresh_seconds:
                target='NORMAL';reason=['Fresh authenticated telemetry observations']
            elif s.stable_since and (occurred-utc(s.stable_since)).total_seconds()>=rules.recovery_seconds and s.healthy_count>=rules.recovery_observations:
                ml_fresh=s.ml_available and s.last_ml_at and (now-utc(s.last_ml_at)).total_seconds()<=rules.ml_fresh_seconds
                if ml_fresh:target='NORMAL';reason=['Sustained positive recovery evidence and available ML; not attack-free proof']
                else:suppressed=True;reason=['Recovery blocked: ML absent, stale or unavailable']
        if s.last_ml_at and (now-utc(s.last_ml_at)).total_seconds()>rules.ml_fresh_seconds and not attack:
            s.ml_available=False;target='UNKNOWN';reason=['ML evidence stale; protection retained']
        if s.last_telemetry_at and (now-utc(s.last_telemetry_at)).total_seconds()>rules.telemetry_fresh_seconds and not attack:
            target='UNKNOWN';reason=['Authenticated telemetry stale; guard retained']
        elif not s.last_telemetry_at and not attack and signal.source=='ml':
            target='UNKNOWN';reason=['No confirmed telemetry baseline']
        if target in LEVEL and LEVEL[target]<LEVEL[s.guard] and target!='NORMAL':target=s.guard
        if target=='NORMAL' and s.guard!='NORMAL' and not (healthy and s.healthy_count>=rules.recovery_observations and s.stable_since and (occurred-utc(s.stable_since)).total_seconds()>=rules.recovery_seconds and s.ml_available):
            target=s.risk;suppressed=True;reason=['Insufficient positive recovery evidence']
        if target!=s.risk and not critical:
            elapsed=(now-utc(s.changed_at)).total_seconds() if s.changed_at else float('inf')
            since=(now-utc(s.last_decision_at)).total_seconds() if s.last_decision_at else float('inf')
            # Fast confirmed escalation bypasses cooldown; downgrades/sideways do not.
            escalating=target in LEVEL and LEVEL[target]>LEVEL[s.guard]
            if (not escalating and elapsed<rules.cooldown_seconds) or since<rules.min_decision_seconds:
                target=s.risk;suppressed=True;reason=['Transition suppressed by cooldown/rate limit']
        if target!=s.risk:
            if target not in ALLOWED[s.risk]:raise ValueError('Forbidden transition')
            s.risk=target;s.changed_at=now.isoformat()
        if s.risk in LEVEL:s.guard=s.risk
    emit=(not s.last_decision_at or (now-utc(s.last_decision_at)).total_seconds()>=rules.min_decision_seconds
          or (signal.category=='security_violation' and signal.trust in {'verified','simulation'}))
    if emit:s.last_decision_at=now.isoformat()
    used=list(dict.fromkeys(used+[e['event_id'] for e in s.evidence]+s.healthy_evidence))
    recommended_state='WATCH' if signal.source=='ml' and signal.category=='anomaly' and diagnostic=='accepted' and LEVEL.get(s.risk,0)<1 else s.risk
    profile=rules.elevated_profile if s.guard in {'ALERT','CRITICAL'} else rules.minimum_profile
    protection=recommend(profile,capabilities,rules.minimum_profile,simulation=mode=='SIMULATION')
    return s,dict(current_state=previous,observed_risk=s.risk,recommended_state=recommended_state,
        reasons=reason or ['Evidence recorded; no transition'],used_signals=used,mode=mode,
        decision_at=now.isoformat(),diagnostic=diagnostic,suppressed=suppressed,emit_decision=emit,
        transitioned=previous!=s.risk,recommended_protection=protection,applicable=False,
        execution_status='simulated' if mode=='SIMULATION' else protection['status'],
        applied_configuration=None,effective_security_state='unconfirmed',trusted_detector=False)

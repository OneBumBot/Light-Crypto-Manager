"""Deterministic policy experiment, synthetic events only; no databases or MQTT."""
import argparse
from dataclasses import replace
from datetime import datetime,timedelta,timezone
import json
import uuid
from .engine import State,evaluate
from .rules import Rules
from .signals import Signal,from_ml
from .profiles import ASCON
from .control_contract import Command,AckSimulator

T=datetime(2026,1,1,tzinfo=timezone.utc)


def event(n,category='accepted',source='protocol',device='sim-device',*,anomaly=False):
    at=T+timedelta(seconds=n)
    if source=='ml':
        row=dict(id=str(uuid.uuid5(uuid.NAMESPACE_URL,'ml:'+str(n))),device_id=device,key_epoch=1,
            sequence_number=n+1,model_id='synthetic',model_version='1.0.0',feature_version='telemetry-causal-v1',
            detector='telemetry_anomaly',status='ok' if category!='unavailable' else 'dead',score=2.0 if anomaly else 0.1,
            threshold=1.0,is_anomaly=anomaly,evaluated_at=at,available_at=at)
        model=dict(model_id='synthetic',model_version='1.0.0',feature_version='telemetry-causal-v1',detector='telemetry_anomaly',
            mode='RESEARCH',score_semantics='Synthetic model-specific deviation, not probability',score_upper_bound=None)
        return from_ml(row,model,at)
    return Signal('sim:'+str(n)+':'+category,source,category,at.isoformat(),at.isoformat(),device,1,n+1,
        'simulation','simulation' if source!='system' else 'monitor')


def scenarios():
    normal=[event(0,'normal','ml')]+[event(n) for n in range(1,62,10)]
    replay=[event(n,'replay') for n in [1,2,3]]
    recovery=replay+[event(n) for n in range(10,341,10)]+[event(345,'normal','ml'),event(350)]
    return {
        'normal':normal,
        'single_physical':[event(0),event(1,'physical_anomaly','rule'),event(2)],
        'physical_series':[event(n,'physical_anomaly','rule') for n in [1,2,3]],
        'replay_series':replay,
        'verified_security_violation':[event(1,'security_violation')],
        'ml_unavailable':replay+[event(10,'unavailable','ml'),event(20)],
        'stale_ml':[event(0,'anomaly','ml',anomaly=True),event(300)],
        'conflicting_sources':[event(0),event(1,'anomaly','ml',anomaly=True),event(2)],
        'recovery':recovery,
        'oscillation':[event(0,'normal','ml')]+[e for n in range(8) for e in [
            event(n*10+1,'physical_anomaly','rule'),event(n*10+2,'normal','ml'),
            event(n*10+3),event(n*10+4),event(n*10+5)]],
        'missing_events':[event(0),event(500),event(1000)],
        'unsupported_profile':replay,
        'missing_ack':replay,
    }


def run(name,events,strategy):
    rules=Rules(strategy=strategy,elevated_profile='simulated-profile',
        cooldown_seconds=30 if strategy=='adaptive_hysteresis' else 0,
        recovery_seconds=300 if strategy=='adaptive_hysteresis' else 1,
        recovery_observations=6 if strategy=='adaptive_hysteresis' else 2,
        watch_observations=2 if strategy=='adaptive_hysteresis' else 1,
        alert_observations=3 if strategy=='adaptive_hysteresis' else 2)
    if name=='unsupported_profile':rules=replace(rules,elevated_profile='unavailable-profile')
    state=State();trace=[];changes=0;last_profile=ASCON;reaction=None;first_trigger=None
    expected_security=name in {'replay_series','verified_security_violation','recovery','ml_unavailable','unsupported_profile','missing_ack'}
    unexpected=0
    for signal in events:
        now=T+timedelta(seconds=300) if name=='stale_ml' and signal.source=='ml' else datetime.fromisoformat(signal.received_at)
        if signal.category in {'replay','security_violation'} and first_trigger is None:first_trigger=now
        state,result=evaluate(state,signal,rules,now,mode='SIMULATION')
        if result['transitioned'] and state.risk in {'WATCH','ALERT','CRITICAL'} and not expected_security:unexpected+=1
        profile=result['recommended_protection']['profile_id']
        if profile!=last_profile:changes+=1;last_profile=profile
        if reaction is None and state.risk in {'ALERT','CRITICAL'} and first_trigger:reaction=(now-first_trigger).total_seconds()
        trace.append(dict(event_id=signal.event_id,**result))
    return dict(scenario=name,strategy=strategy,policy_version='simulation-v1-'+strategy,rules=rules.payload(),mode='SIMULATION',synthetic=True,
        decisions=len(trace),risk_transitions=sum(r['transitioned'] for r in trace),
        suppressed=sum(r['suppressed'] for r in trace),modeled_recommendation_changes=changes,
        unexpected_risk_escalations=unexpected,reaction_seconds=reaction,applied_changes=0,
        final_risk=state.risk,trace=trace)


def experiment():
    results=[run(name,items,strategy) for name,items in scenarios().items()
        for strategy in ['fixed','adaptive','adaptive_research','adaptive_hysteresis']]
    return dict(schema_version=1,mode='SIMULATION',seed='no randomness; fixed UTC clock',
        interpretation='Synthetic policy-control comparison, not attack detection or cryptographic strength',results=results)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);args=p.parse_args()
    from pathlib import Path
    Path(args.output).write_text(json.dumps(experiment(),indent=2,allow_nan=False)+'\n')
    print('SIMULATION ONLY: deterministic policy experiment saved; no device changes')

if __name__=='__main__':main()

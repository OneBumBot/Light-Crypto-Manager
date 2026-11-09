from dataclasses import replace
from datetime import datetime,timedelta,timezone
import uuid
import pytest
from src.policy.signals import Signal
from src.policy.engine import State,evaluate
from src.policy.rules import Rules
from src.policy.profiles import recommend,registry,ASCON
from src.policy.control_contract import Command,AckSimulator

T=datetime(2026,1,1,tzinfo=timezone.utc)

def sig(n,category='accepted',source='protocol',device='alpha',**kwargs):
    return Signal('test:'+str(n),source,category,(T+timedelta(seconds=n)).isoformat(),
        (T+timedelta(seconds=n)).isoformat(),device,1,n+1,'authenticated',
        'verified' if source!='ml' else 'monitor',**kwargs)


def step(s,n,category='accepted',rules=None,**kw):
    return evaluate(s,sig(n,category,**kw),rules or Rules(),T+timedelta(seconds=n))


def test_replay_confirmation_critical_and_preserved_configuration():
    s=State()
    s,d=step(s,1,'replay');assert s.risk=='UNKNOWN'
    s,d=step(s,2,'replay');assert s.risk=='WATCH'
    s,d=step(s,3,'replay');assert s.risk=='ALERT'
    s,d=step(s,4,'security_violation');assert s.risk=='CRITICAL'
    assert d['applicable'] is False and d['applied_configuration'] is None
    assert d['recommended_protection']['profile_id']==ASCON


def test_physical_anomaly_is_watch_not_attack_and_device_isolation():
    s,d=step(State(),1,'physical_anomaly',source='rule')
    assert s.risk=='WATCH' and 'not a confirmed cyberattack' in d['reasons'][0]
    assert State().risk=='UNKNOWN'


def test_stale_late_future_and_unattributed_do_not_target():
    s,d=step(State(),10)
    for signal,now,diagnostic in [(sig(1),T+timedelta(seconds=11),'late'),
          (sig(1),T+timedelta(seconds=300),'stale'),(sig(300),T,'future')]:
        new,d=evaluate(s,signal,Rules(),now);assert d['diagnostic']==diagnostic and new.risk==s.risk
    signal=Signal('rejected:1','protocol','rejected',T.isoformat(),T.isoformat())
    _,d=evaluate(State(),signal,Rules(),T);assert d['diagnostic']=='unattributed'
    with pytest.raises(ValueError):replace(signal,device_id='victim').validate()
    with pytest.raises(ValueError):replace(sig(1),schema_version=True).validate()


def test_positive_recovery_requires_continuous_history_and_available_ml():
    s=State(risk='ALERT',guard='ALERT',changed_at=T.isoformat())
    rules=Rules(recovery_seconds=30,cooldown_seconds=10,recovery_observations=3,telemetry_fresh_seconds=15)
    for n in [1,11,21,31]:s,d=step(s,n,rules=rules)
    assert s.risk=='ALERT' and d['suppressed']
    s.ml_available=True;s.last_ml_at=(T+timedelta(seconds=31)).isoformat()
    s,d=step(s,32,rules=rules);assert s.risk=='NORMAL'
    s=State(risk='ALERT',guard='ALERT',ml_available=True,last_ml_at=T.isoformat())
    for n in [1,101,201]:s,d=step(s,n,rules=rules)
    assert s.risk!='NORMAL'  # gaps cannot count as a stable observed period


def test_cooldown_rate_limit_and_critical_bypass():
    rules=Rules(min_decision_seconds=10)
    s=State(risk='NORMAL',changed_at=T.isoformat(),last_decision_at=T.isoformat())
    s,d=step(s,1,'physical_anomaly',source='rule',rules=rules)
    assert s.risk=='NORMAL' and d['suppressed']
    s,d=step(s,2,'security_violation',rules=rules);assert s.risk=='CRITICAL'
    s,d=step(s,3,'unavailable',source='system',rules=rules);assert s.risk=='CRITICAL' and d['suppressed']


def test_unknown_preserves_guard_and_no_empty_queue_recovery():
    s=State(risk='ALERT',guard='ALERT')
    s,d=step(s,1,'unavailable',source='system');assert s.risk=='UNKNOWN' and s.guard=='ALERT'
    assert d['recommended_protection']['profile_id']==ASCON
    s,d=step(s,2);assert s.risk=='UNKNOWN'


def test_profile_registry_minimum_and_capabilities():
    assert [p['profile_id'] for p in registry()]==[ASCON]
    for profile in ['magma','CRISP','unknown','plaintext']:
        assert recommend(profile,('mqtt_tls','aead','telemetry_v2'))['status']=='unsupported_profile'
    assert recommend(ASCON,('aead',))['status']=='minimum_protection_violation'
    assert recommend(ASCON,('mqtt_tls','aead','telemetry_v2'))['applicable'] is False
    assert recommend('simulated-profile',('mqtt_tls','aead','telemetry_v2'))['status']=='unsupported_profile'
    assert recommend('simulated-profile',('mqtt_tls','aead','telemetry_v2'),simulation=True)['status']=='simulated'


def test_rules_reject_executable_unknown_and_bad_ranges():
    for payload in [{'expression':'__import__("os")'},{'cooldown_seconds':True},{'alert_observations':999},
                    {'strategy':'eval'},{'recovery_seconds':1,'cooldown_seconds':30}]:
        with pytest.raises(ValueError):Rules.parse(payload)


def test_command_contract_auth_replay_ttl_and_no_applied():
    c=Command(str(uuid.uuid4()),'alpha','set_profile',ASCON,'v1',T.isoformat(),
       (T+timedelta(seconds=30)).isoformat(),1,1,str(uuid.uuid4()),str(uuid.uuid4()))
    sim=AckSimulator()
    with pytest.raises(ValueError):sim.acknowledge(c,T)
    ack=sim.acknowledge(c,T,authentic=True)
    assert ack['status']=='simulated' and ack['applied_configuration'] is None
    with pytest.raises(ValueError):sim.acknowledge(c,T,authentic=True)
    with pytest.raises(ValueError):AckSimulator().acknowledge(c,T+timedelta(seconds=31),authentic=True)
    with pytest.raises(ValueError):AckSimulator().acknowledge(replace(c,requested_profile='magma'),T,authentic=True)

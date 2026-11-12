"""Real PostgreSQL golden equivalence, ordering, activation and rollback behavior."""
import json,uuid,time
from dataclasses import replace
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace
import pytest
from sqlalchemy import select,text,func,delete
from src.policy import models as m
from src.policy.state import install,process
from src.policy.rules import Rules
from src.security_events import journal,capture,queue
from policy13_vectors import T,traces,event
from policy13_reference import process as sequential
pytestmark=pytest.mark.postgres
GOLDEN_RESULTS=[]


def normalize(value):
    if isinstance(value,dict):return {k:normalize(v) for k,v in value.items() if k not in ['id','compute_ms','command_id','correlation_id','acknowledgement_id']}
    if isinstance(value,list):return [normalize(v) for v in value]
    return value


@pytest.mark.parametrize('trace',traces(),ids=lambda t:t[0])
def test_golden_sequential_vs_optimized(postgres_db,trace):
    from src.policy.state import BatchRules
    e=postgres_db.db.engine;name,initial,rules,events=trace
    results=[]
    for impl in [sequential,process]:
        with e.begin() as c:
            for table in [m.intents,m.transitions,m.decisions,m.signals,m.states,m.command_counters]:c.execute(delete(table))
            install(c,'golden',rules.payload(),T,activate=True)
            c.execute(m.states.insert().values(device_id='alpha',version='golden',state=initial.payload(),observed_risk=initial.risk,updated_at=T))
        output=[]
        for n,s in enumerate(events):
            now=T+timedelta(seconds=max(n,int((__import__('src.policy.signals',fromlist=['utc']).utc(s.received_at)-T).total_seconds())))
            with e.begin() as c:output.append(normalize(impl(c,s,'golden',now,**({'batch_rules':BatchRules('golden',rules)} if impl is process else {}))))
        with e.connect() as c:
            final=dict(c.execute(select(m.states)).mappings().one())
            statuses=[tuple(r) for r in c.execute(select(m.signals.c.event_id,m.signals.c.status).order_by(m.signals.c.event_id))]
            transitions=[tuple(r) for r in c.execute(select(m.transitions.c.from_state,m.transitions.c.to_state).order_by(m.transitions.c.at))]
            assert final['applied'] is None and final['effective_security_state']=='unconfirmed'
        results.append((output,normalize(final),statuses,transitions))
    assert results[0]==results[1]
    GOLDEN_RESULTS.append(dict(trace=name,sequential=results[0],optimized=results[1],equal=True))


def setup(e):
    with e.begin() as c:install(c,'v1',Rules(min_decision_seconds=0).payload(),T,activate=True)


def add(c,n,seconds=None,device='alpha',category='accepted'):
    from sqlalchemy.dialects.postgresql import insert
    identity=str(uuid.UUID(int=n+1));c.execute(journal.insert().values(id=identity,source='protocol',category=category,device_id=device,key_epoch=1,sequence_number=n+1,occurred_at=T+timedelta(seconds=n if seconds is None else seconds)))
    c.execute(insert(queue).values(id=1,retained=1).on_conflict_do_update(index_elements=['id'],set_={'retained':queue.c.retained+1}))
    return 'security:'+identity


def test_late_insert_is_discovered_and_audited(postgres_db):
    from src.policy.worker import poll_batch
    e=postgres_db.db.engine;setup(e)
    with e.begin() as c:first=add(c,10)
    assert poll_batch(e,at=T+timedelta(seconds=11))==1
    with e.begin() as c:late=add(c,5)
    assert poll_batch(e,at=T+timedelta(seconds=12))==1
    with e.connect() as c:
        assert c.scalar(select(m.signals.c.status).where(m.signals.c.event_id==late))=='late'
        assert c.scalar(select(m.states.c.state))['last_event_at']==(T+timedelta(seconds=10)).isoformat()
        assert c.scalar(select(func.count()).select_from(m.signals))==2


@pytest.mark.parametrize('workers,devices',[(2,1),(4,10)])
def test_parallel_workers_serialize_without_skipping_device_order(postgres_db,workers,devices):
    from src.policy.worker import poll_batch
    e=postgres_db.db.engine;setup(e)
    with e.begin() as c:
        for n in reversed(range(100)):add(c,n,device='dev'+str(n%devices))
    def run(_):
        while poll_batch(e,limit=16,at=T+timedelta(seconds=110)):pass
    with ThreadPoolExecutor(max_workers=workers) as pool:list(pool.map(run,range(workers)))
    with e.connect() as c:
        assert c.scalar(select(func.count()).select_from(m.signals))==100
        assert c.scalar(select(func.count()).select_from(m.signals).where(m.signals.c.status=='late'))==0
        assert c.scalar(select(func.sum(m.states.c.revision)))==100
        for device,state in c.execute(select(m.states.c.device_id,m.states.c.state)):
            expected=max(n for n in range(100) if 'dev'+str(n%devices)==device)
            assert state['last_event_at']==(T+timedelta(seconds=expected)).isoformat()
            assert state['healthy_count']==100//devices


def test_batch_rollback_and_retry_leave_no_partial_fsm_or_marker(postgres_db):
    from src.policy.worker import poll_batch
    from src.policy.models import pending
    e=postgres_db.db.engine;setup(e)
    with e.begin() as c:
        for n in range(4):add(c,n,category='replay')
    def fail():raise RuntimeError('Injected before commit')
    with pytest.raises(RuntimeError,match='Injected'):
        poll_batch(e,at=T+timedelta(seconds=5),before_commit=fail)
    with e.connect() as c:
        assert c.scalar(select(func.count()).select_from(pending))==4
        for table in [m.states,m.signals,m.decisions,m.intents,m.transitions]:assert c.scalar(select(func.count()).select_from(table))==0
    assert poll_batch(e,at=T+timedelta(seconds=5))==4
    with e.connect() as c:snapshot=[c.scalar(select(func.count()).select_from(t)) for t in [m.states,m.signals,m.decisions,m.intents,m.transitions]]
    assert poll_batch(e,at=T+timedelta(seconds=5))==0
    with e.connect() as c:assert snapshot==[c.scalar(select(func.count()).select_from(t)) for t in [m.states,m.signals,m.decisions,m.intents,m.transitions]]


def test_version_activation_waits_for_batch_and_retains_all_sources(postgres_db):
    from src.policy.worker import poll_batch
    e=postgres_db.db.engine;setup(e);claimed=Event();release=Event()
    with e.begin() as c:
        for n in range(8):add(c,n,category='replay')
    def pause():claimed.set();assert release.wait(5)
    def activate():
        with e.begin() as c:install(c,'v2',Rules(watch_observations=3,alert_observations=4).payload(),T+timedelta(seconds=10),activate=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first=pool.submit(poll_batch,e,limit=4,at=T+timedelta(seconds=9),after_claim=pause)
        assert claimed.wait(5);second=pool.submit(activate);time.sleep(.1);assert not second.done();release.set();assert first.result()==4;second.result()
    while poll_batch(e,at=T+timedelta(seconds=11)):pass
    with e.connect() as c:
        assert dict(c.execute(select(m.signals.c.version,func.count()).group_by(m.signals.c.version)).all())=={'v1':4,'v2':8}
        assert c.scalar(select(m.states.c.state).where(m.states.c.version=='v2'))['guard'] in ['WATCH','ALERT']
        assert c.scalar(select(m.versions.c.active).where(m.versions.c.version=='v2')) is True
        assert c.scalar(select(m.decisions.c.result).where(m.decisions.c.version=='v2').limit(1))['policy_version']=='v2'


def test_retention_never_removes_pending_and_preserves_identity(postgres_db):
    from src.policy.worker import poll_batch,prune_journal
    from src.policy.state import prune
    e=postgres_db.db.engine;setup(e)
    with e.begin() as c:
        for n in range(3):add(c,n)
        assert prune_journal(c,1,T+timedelta(days=3))==0
    assert poll_batch(e,limit=2,at=T+timedelta(seconds=5))==2
    with e.begin() as c:
        assert prune_journal(c,1,T+timedelta(days=3))==2
        prune(c,1,T+timedelta(days=3))
    assert poll_batch(e,at=T+timedelta(seconds=5))==1
    with e.connect() as c:assert c.scalar(select(func.count()).select_from(m.signals))==3


def test_synthetic_stale_waits_for_committed_backlog_and_is_bounded(postgres_db):
    from src.policy.worker import poll_batch
    e=postgres_db.db.engine;setup(e)
    with e.begin() as c:
        process(c,event(0),'v1',T)
        process(c,event(1,'replay'),'v1',T+timedelta(seconds=1))
        process(c,event(2,'replay'),'v1',T+timedelta(seconds=2))
        add(c,20,seconds=-80);add(c,21,seconds=90)
    ticks=iter([T+timedelta(seconds=100),T+timedelta(seconds=100,milliseconds=10)])
    assert poll_batch(e,limit=1,at=lambda:next(ticks))==1
    with e.connect() as c:assert not list(c.scalars(select(m.signals.c.event_id).where(m.signals.c.event_id.like('stale:%'))))
    assert poll_batch(e,limit=1,at=T+timedelta(seconds=100))==1
    assert poll_batch(e,at=T+timedelta(seconds=200))==1
    for _ in range(4):assert poll_batch(e,at=T+timedelta(seconds=200))==0
    with e.connect() as c:
        assert c.scalar(select(func.count()).select_from(m.signals).where(m.signals.c.event_id.like('stale:%')))==1
        assert c.scalar(select(m.states.c.state))['guard']=='WATCH'


def test_new_version_uses_its_rules_and_context_cannot_cross_version(postgres_db):
    from src.policy.worker import poll_batch
    from src.policy.state import BatchRules
    e=postgres_db.db.engine;setup(e)
    with e.begin() as c:
        for n in range(2):add(c,n,category='replay')
    assert poll_batch(e,at=T+timedelta(seconds=3))==2
    with e.begin() as c:
        install(c,'fixed',Rules(strategy='fixed',min_decision_seconds=0).payload(),T+timedelta(seconds=4),activate=True)
        for n in range(2,5):add(c,n,category='replay')
    while poll_batch(e,at=T+timedelta(seconds=5)):pass
    with e.connect() as c:
        assert c.scalar(select(m.states.c.state).where(m.states.c.version=='fixed'))['guard']=='WATCH'
        assert c.scalar(select(func.count()).select_from(m.decisions).where(m.decisions.c.version=='fixed'))==5
    with pytest.raises(ValueError,match='mismatch'):
        with e.begin() as c:process(c,event(6),'fixed',T+timedelta(seconds=6),batch_rules=BatchRules('v1',Rules()))


def test_retry_restart_does_not_duplicate_proposed_intent_or_guard(postgres_db):
    from src.policy.worker import poll_batch
    e=postgres_db.db.engine
    with e.begin() as c:
        install(c,'v1',Rules(min_decision_seconds=0,elevated_profile='simulated-future').payload(),T,activate=True)
        for n in range(4):add(c,n,category='replay')
    assert poll_batch(e,at=T+timedelta(seconds=5))==4
    with e.connect() as c:
        before=c.execute(select(m.states.c.state,m.states.c.revision,m.states.c.requested)).one()
        assert c.scalar(select(func.count()).select_from(m.intents))==1
        assert c.scalar(select(m.intents.c.status))=='unsupported'
    # Re-activation replays retained sources only if not already consumed.
    with e.begin() as c:install(c,'v1',Rules(min_decision_seconds=0,elevated_profile='simulated-future').payload(),T+timedelta(seconds=6),activate=True)
    for _ in range(3):assert poll_batch(e,at=T+timedelta(seconds=6))==0
    with e.connect() as c:
        assert c.execute(select(m.states.c.state,m.states.c.revision,m.states.c.requested)).one()==before
        assert c.scalar(select(func.count()).select_from(m.intents))==1
        assert c.scalar(select(func.count()).select_from(m.decisions))==4


def test_silent_device_stale_detection_survives_other_device_backlog(postgres_db):
    from src.policy.worker import poll_batch
    from src.policy.engine import State
    e=postgres_db.db.engine;setup(e)
    with e.begin() as c:
        initial=State(risk='WATCH',guard='WATCH',last_telemetry_at=T.isoformat())
        c.execute(m.states.insert().values(device_id='beta',version='v1',state=initial.payload(),observed_risk='WATCH',updated_at=T))
        for n in range(3):add(c,n,seconds=90+n)
    poll_batch(e,limit=1,at=T+timedelta(seconds=100))
    with e.connect() as c:
        assert c.scalar(select(m.states.c.state).where(m.states.c.device_id=='beta'))['risk']=='UNKNOWN'
        assert c.scalar(select(m.states.c.state).where(m.states.c.device_id=='beta'))['guard']=='WATCH'
        assert c.scalar(select(func.count()).select_from(m.signals).where(m.signals.c.event_id.like('stale:%')))==1


def ml_source(c,n,*,status='warmup',device='alpha',epoch=1,feature='telemetry-causal-v1',model='p13'):
    from src.ml_storage import events
    ident=str(uuid.UUID(int=100000+n))
    c.execute(events.insert().values(id=ident,device_id=device,key_epoch=epoch,sequence_number=n+1,model_id=model,model_version='v1',feature_version=feature,detector='telemetry_anomaly',status=status,available_at=T+timedelta(seconds=n),evaluated_at=T+timedelta(seconds=n)))
    return ident


def ml_setup(c):
    from src.devices import devices
    from src.ml_storage import models
    c.execute(devices.insert().values(device_id='alpha',database_device_id=900,topic='iot/sensors/alpha',key_epoch=1,crypto_profile='Ascon-AEAD128'))
    c.execute(models.insert().values(model_id='p13',model_version='v1',status='available',heartbeat_at=T,feature_version='telemetry-causal-v1',detector='telemetry_anomaly',mode='RESEARCH',score_semantics='statistical research score; not attack probability',score_upper_bound=1))


def test_ml_security_fairness_and_status_updates_remain_untrusted(postgres_db):
    from src.policy.worker import poll_batch
    from src.ml_storage import events
    e=postgres_db.db.engine;setup(e)
    with e.begin() as c:
        ml_setup(c)
        for n in range(40):add(c,n)
        mlid=ml_source(c,1);c.execute(events.update().where(events.c.id==mlid).values(status='retry'))
    assert poll_batch(e,limit=4,at=T+timedelta(seconds=50))==4
    with e.connect() as c:
        rows=list(c.execute(select(m.signals.c.event_id,m.signals.c.payload)))
        assert sum(eid.startswith('ml:') for eid,_ in rows)==2
        for eid,payload in rows:
            if eid.startswith('ml:'):
                assert payload['trust']=='monitor' and payload['original']['trusted_detector'] is False
                assert payload['original']['score'] is None
        assert c.scalar(select(m.states.c.state))['risk']!='NORMAL'
    while poll_batch(e,at=T+timedelta(seconds=50)):pass
    with e.connect() as c:assert c.scalar(select(func.count()).select_from(m.signals))==42


@pytest.mark.parametrize('change',[{'device':'unknown'},{'epoch':2},{'feature':'unsupported'},{'model':'missing'}])
def test_ml_contract_rejection_is_durable_and_never_authenticated(postgres_db,change):
    from src.policy.worker import poll_batch
    e=postgres_db.db.engine;setup(e)
    with e.begin() as c:ml_setup(c);ml_source(c,1,**change)
    assert poll_batch(e,at=T+timedelta(seconds=2))==1
    with e.connect() as c:
        assert c.scalar(select(m.signals.c.status))=='rejected'
        assert c.scalar(select(m.signals.c.device_id)) is None
        assert c.scalar(select(func.count()).select_from(m.states))==0


def test_policy_observations_cannot_create_live_control_commands(postgres_db,registry):
    from test_control_storage import setup as control_setup,baseline
    from src.device_control import models as control
    from src.policy.worker import poll_batch
    web=postgres_db;control_setup(web,registry);baseline(web,registry);e=web.db.engine;setup(e)
    with e.begin() as c:
        for n in range(4):add(c,n,device='raspb1',category='replay')
    while poll_batch(e,at=T+timedelta(seconds=6)):pass
    with e.connect() as c:
        assert c.scalar(select(func.count()).select_from(control.commands))==0
        assert c.scalar(select(func.count()).select_from(control.transitions))==0
        assert c.scalar(select(m.states.c.applied)) is None
        assert c.scalar(select(control.devices.c.effective_profile))=='ascon-aead128-v1'


def test_full_queue_golden_matches_original_sequential_fair_poll(postgres_db):
    from policy13_worker_reference import poll as original_poll
    from src.policy.worker import poll_batch
    from src.policy.work_queue import seed
    from src.devices import devices
    from src.ml_storage import models
    e=postgres_db.db.engine;setup(e)
    with e.begin() as c:
        c.execute(models.insert().values(model_id='p13',model_version='v1',status='available',heartbeat_at=T,feature_version='telemetry-causal-v1',detector='telemetry_anomaly',mode='RESEARCH',score_semantics='research only',score_upper_bound=1))
        for n in range(10):
            device='dev'+str(n)
            c.execute(devices.insert().values(device_id=device,database_device_id=1000+n,topic='iot/sensors/'+device,key_epoch=1,crypto_profile='Ascon-AEAD128'))
            ml_source(c,n,device=device)
        for n in reversed(range(100)):add(c,n,seconds=n//4,device='dev'+str(n%10),category='replay' if n%3==0 else 'accepted')
    def output():
        with e.connect() as c:
            return dict(states=[normalize(dict(v)) for v in c.execute(select(m.states).order_by(m.states.c.device_id)).mappings()],
                signals=[tuple(v) for v in c.execute(select(m.signals.c.event_id,m.signals.c.status).order_by(m.signals.c.event_id))],
                decisions=[normalize(dict(v)) for v in c.execute(select(m.decisions).order_by(m.decisions.c.event_id)).mappings()],
                transitions=[tuple(v) for v in c.execute(select(m.transitions.c.device_id,m.transitions.c.from_state,m.transitions.c.to_state).order_by(m.transitions.c.device_id,m.transitions.c.at,m.transitions.c.to_state))])
    for index in range(110):assert original_poll(e,prefer_ml=bool(index%2),at=T+timedelta(seconds=40))
    expected=output()
    with e.begin() as c:
        for table in [m.intents,m.transitions,m.decisions,m.signals,m.states,m.command_counters,m.pending]:c.execute(delete(table))
        seed(c,'v1')
    while poll_batch(e,limit=17,at=T+timedelta(seconds=40),maintenance=False):pass
    actual=output();assert actual==expected
    GOLDEN_RESULTS.append(dict(trace="full-queue-110-security-ml",sequential=expected,optimized=actual,equal=True))
    with e.connect() as c:
        assert c.scalar(select(func.count()).select_from(m.signals))==110
        assert c.scalar(select(func.count()).select_from(m.decisions).where(m.decisions.c.result['trusted_detector'].as_boolean().is_(True)))==0


def test_metrics_show_real_evidence_lag_and_overflow_not_heartbeat(postgres_db):
    from src.policy.worker import poll_batch,heartbeat
    from src.policy.diagnostics import snapshot
    e=postgres_db.db.engine
    with e.begin() as c:
        now=c.scalar(select(func.clock_timestamp()));install(c,'metrics',Rules().payload(),now,activate=True)
        first=capture(c,'accepted',SimpleNamespace(device_id='alpha',key_epoch=1,sequence_number=1),now-timedelta(seconds=180))
    poll_batch(e,at=now);heartbeat(e)
    with e.begin() as c:
        capture(c,'replay',SimpleNamespace(device_id='alpha',key_epoch=1,sequence_number=2),now-timedelta(seconds=160))
        c.execute(queue.update().values(capacity=2))
        assert capture(c,'rejected',now=now) is None
        d=snapshot(c,c.scalar(select(func.clock_timestamp())))
        assert d['worker_status']=='ready' and d['heartbeat_age_seconds']<1
        assert d['source_lag_seconds']>=179 and d['evidence_status']=='stale'
        assert d['backlog_status']=='lagging' and d['security_queue_pending']==1
        assert d['overflow']==1 and d['capacity_utilization']==1


def test_lock_timeout_does_not_skip_first_event_or_leave_claim(postgres_db):
    from contextlib import contextmanager
    from sqlalchemy.exc import DBAPIError
    from src.policy.worker import poll_batch
    e=postgres_db.db.engine;setup(e)
    with e.begin() as c:add(c,0);add(c,1)
    class DeadlineEngine:
        @contextmanager
        def begin(self):
            with e.begin() as c:
                c.execute(text("SET LOCAL lock_timeout='50ms'"));yield c
    with e.begin() as c:
        c.execute(select(m.pending).order_by(m.pending.c.event_id).limit(1).with_for_update()).all()
        with pytest.raises(DBAPIError):poll_batch(DeadlineEngine(),at=T+timedelta(seconds=2))
    assert poll_batch(e,at=T+timedelta(seconds=2))==2
    with e.connect() as c:
        assert c.scalar(select(m.states.c.state))['healthy_count']==2
        assert c.scalar(select(func.count()).select_from(m.signals))==2


def test_pending_source_retention_race_is_serialized(postgres_db):
    from src.policy.worker import poll_batch,prune_journal
    e=postgres_db.db.engine;setup(e);claimed=Event();release=Event()
    with e.begin() as c:
        for n in range(4):add(c,n)
    def pause():claimed.set();assert release.wait(5)
    def prune():
        with e.begin() as c:return prune_journal(c,1,T+timedelta(days=3))
    with ThreadPoolExecutor(max_workers=2) as pool:
        f=pool.submit(poll_batch,e,limit=2,at=T+timedelta(seconds=5),after_claim=pause)
        assert claimed.wait(5);g=pool.submit(prune);time.sleep(.1);assert not g.done();release.set();assert f.result()==2;assert g.result()==2
    assert poll_batch(e,at=T+timedelta(seconds=5))==2
    with e.connect() as c:assert c.scalar(select(func.count()).select_from(m.signals))==4


def test_upgrade_from_0010_preserves_existing_authorities_and_is_idempotent(legacy_postgres_db,registry):
    from alembic.config import Config
    from alembic import command
    from src.migrate import upgrade
    from policy13_reference import install as old_install,process as old_process
    from test_control_storage import setup as control_setup,baseline
    from src.device_control import server
    from src.crypto_profiles import AES
    from src.kuz_usage import initialize_fresh,reserve
    web=legacy_postgres_db;e=web.db.engine
    with e.begin() as c:
        config=Config('alembic.ini');config.attributes['connection']=c;command.upgrade(config,'0010_mgm_key_usage')
        old_install(c,'active',Rules().payload(),T,activate=True);old_install(c,'inactive',Rules(strategy='fixed').payload(),T)
        old_process(c,event(1,'replay'),'active',T+timedelta(seconds=1));old_process(c,event(2,'replay'),'active',T+timedelta(seconds=1))
        capture(c,'rejected',now=T)
        initialize_fresh(c,'budget-test',1);reserve(c,'budget-test',1,str(uuid.uuid4()),1,100)
    control_setup(web,registry);baseline(web,registry)
    with e.begin() as c:server.request_switch(c,'raspb1',AES,'admin:upgrade-test',mode=server.MODE)
    tables=['policy_versions','policy_device_states','policy_signals','policy_decisions','policy_transitions','policy_control_intents','policy_control_counters','mqtt_replay_state','telemetry_outbox','live_control_devices','live_control_transitions','live_control_commands','live_control_evidence','crypto_key_usage','crypto_usage_reservations']
    def contents():
        with e.connect() as c:return {t:sorted(str(v[0]) for v in c.execute(text('SELECT to_jsonb(t)::text FROM '+t+' t'))) for t in tables}
    before=contents();upgrade(e);assert contents()==before
    with e.connect() as c:
        pending=c.scalar(select(func.count()).select_from(m.pending));assert pending==2
        assert c.scalar(select(func.count()).select_from(m.signals).where(m.signals.c.status=='rate_limited'))==1
    upgrade(e);assert contents()==before
    with e.connect() as c:assert c.scalar(select(func.count()).select_from(m.pending))==pending


def test_direct_state_concurrent_distinct_events_never_lose_evidence(postgres_db):
    from sqlalchemy import event as sql_event
    e=postgres_db.db.engine;setup(e);read=Event();release=Event()
    with e.begin() as c:process(c,event(0),'v1',T)
    def barrier(c,cursor,statement,parameters,context,many):
        if statement.lstrip().startswith('SELECT') and 'FROM policy_device_states' in statement and 'ORDER BY' not in statement and not read.is_set():
            read.set();assert release.wait(5)
    def attempt(n):
        with e.begin() as c:process(c,event(n),'v1',T+timedelta(seconds=n))
    sql_event.listen(e,'after_cursor_execute',barrier)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first=pool.submit(attempt,1);assert read.wait(5);second=pool.submit(attempt,2);time.sleep(.2);release.set();first.result();second.result()
    finally:sql_event.remove(e,'after_cursor_execute',barrier)
    with e.connect() as c:
        state=c.scalar(select(m.states.c.state))
        assert state['healthy_count']==3 and state['last_event_at']==(T+timedelta(seconds=2)).isoformat()
        assert c.scalar(select(m.states.c.revision))==3


@pytest.mark.parametrize('app_env,authorized,expected',[('test','1',True),('production','1',False),('test','0',False)])
def test_stage13_mgm_authorization_remains_explicit_lab_only(monkeypatch,app_env,authorized,expected):
    from src.kuz_release import validation_enabled
    monkeypatch.setenv('APP_ENV',app_env);monkeypatch.setenv('LCM_KUZ_VALIDATION_AUTHORIZATION',authorized);monkeypatch.setenv('LCM_LAB_PROJECT','lcm-stage13-policy-crypto')
    assert validation_enabled() is expected


def test_ml_internal_fsm_failure_is_not_a_rejected_source(postgres_db,monkeypatch):
    from src.policy import worker
    e=postgres_db.db.engine;setup(e)
    with e.begin() as c:ml_setup(c);ml_source(c,1)
    def fail(*args,**kwargs):raise ValueError('Injected internal FSM failure')
    monkeypatch.setattr(worker,'process',fail)
    with pytest.raises(ValueError,match='internal FSM'):
        worker.poll_batch(e,at=T+timedelta(seconds=2))
    with e.connect() as c:
        assert c.scalar(select(func.count()).select_from(m.pending))==1
        assert c.scalar(select(func.count()).select_from(m.signals))==0

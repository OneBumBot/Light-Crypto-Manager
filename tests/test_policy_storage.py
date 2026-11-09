from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
import uuid
import pytest
from sqlalchemy import select,func,text
from src.policy.state import install,process
from src.policy.rules import Rules
from src.policy.models import versions,states,decisions,signals,transitions,intents
from src.policy.worker import poll,bootstrap
from src.security_events import capture,journal,queue
from test_policy_engine import T,sig

pytestmark=pytest.mark.postgres


def setup(engine,**settings):
    with engine.begin() as c:install(c,'test-v1',Rules(**settings).payload(),T,activate=True)


def test_idempotent_atomic_decision_and_restart(postgres_db):
    engine=postgres_db.db.engine;setup(engine)
    with engine.begin() as c:
        first=process(c,sig(1,'replay'),'test-v1',T+timedelta(seconds=1))
    with engine.begin() as c:assert process(c,sig(1,'replay'),'test-v1',T+timedelta(seconds=2)) is None
    with pytest.raises(RuntimeError):
        with engine.begin() as c:
            process(c,sig(2,'replay'),'test-v1',T+timedelta(seconds=2),before_commit=lambda:(_ for _ in ()).throw(RuntimeError('rollback')))
    with engine.connect() as c:
        assert c.scalar(select(func.count()).select_from(decisions))==1
        assert c.scalar(select(states.c.revision))==1
        assert c.scalar(select(signals.c.event_id))=='test:1'
    with engine.begin() as c:d=process(c,sig(2,'replay'),'test-v1',T+timedelta(seconds=2))
    assert d['observed_risk']=='WATCH'
    with engine.connect() as c:assert c.scalar(select(func.count()).select_from(transitions))==1


def test_concurrent_device_processing_one_event(postgres_db):
    engine=postgres_db.db.engine;setup(engine)
    def attempt(_):
        with engine.begin() as c:return process(c,sig(1,'replay'),'test-v1',T+timedelta(seconds=1))
    with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(attempt,range(16)))
    assert sum(r is not None for r in results)==1
    with engine.connect() as c:
        assert c.scalar(select(states.c.revision))==1
        assert c.scalar(select(func.count()).select_from(decisions))==1


def test_version_immutability_activation_and_minimum(postgres_db):
    engine=postgres_db.db.engine;setup(engine)
    with pytest.raises(ValueError):
        with engine.begin() as c:install(c,'test-v1',Rules(cooldown_seconds=31).payload(),T)
    with pytest.raises(ValueError):
        with engine.begin() as c:install(c,'bad',Rules(minimum_profile='plaintext').payload(),T,activate=True)
    with engine.begin() as c:install(c,'next',Rules().payload(),T,actor='admin:1',activate=True)
    with engine.connect() as c:assert c.scalars(select(versions.c.version).where(versions.c.active.is_(True))).all()==['next']


def test_unsupported_intent_never_applied(postgres_db):
    engine=postgres_db.db.engine;setup(engine,elevated_profile='magma')
    for n in [1,2,3]:
        with engine.begin() as c:result=process(c,sig(n,'replay'),'test-v1',T+timedelta(seconds=n))
    assert result['recommended_protection']['status']=='unsupported_profile'
    with engine.connect() as c:
        assert c.scalar(select(intents.c.status))=='unsupported'
        assert c.scalar(select(states.c.applied)) is None
        assert c.scalar(select(states.c.configured_profile))=='ascon-aead128-v1'


def test_source_journal_bounded_unattributed_and_worker_dedupe(postgres_db):
    from types import SimpleNamespace
    engine=postgres_db.db.engine;bootstrap(engine)
    with engine.begin() as c:
        capture(c,'rejected',now=T)
        capture(c,'replay',SimpleNamespace(device_id='alpha',key_epoch=1,sequence_number=1),T)
        c.execute(queue.update().values(capacity=2))
        assert capture(c,'rejected',now=T) is None
    assert poll(engine) and poll(engine) and not poll(engine)
    with engine.connect() as c:
        assert c.scalar(select(queue.c.overflow))==1
        assert c.scalar(select(func.count()).select_from(decisions))==1
        assert c.scalar(select(journal.c.device_id).where(journal.c.category=='rejected')) is None
        assert c.scalar(select(func.count()).select_from(states))==1


def test_stage6_upgrade_preserves_ml_and_replay(legacy_postgres_db):
    from alembic.config import Config
    from alembic import command
    from src.migrate import upgrade
    engine=legacy_postgres_db.db.engine
    with engine.begin() as c:
        config=Config('alembic.ini');config.attributes['connection']=c;command.upgrade(config,'0004_ml')
        c.execute(text("INSERT INTO mqtt_replay_state VALUES ('receiver','policy-migration',1,51)"))
        c.execute(text("INSERT INTO ml_models(model_id,model_version,status,heartbeat_at) VALUES ('preserved','v1','disabled',:now)"),{'now':T})
    upgrade(engine);upgrade(engine)
    with engine.connect() as c:
        assert c.scalar(text("SELECT last_sequence FROM mqtt_replay_state WHERE device_id='policy-migration'"))==51
        assert c.scalar(text("SELECT status FROM ml_models WHERE model_id='preserved'"))=='disabled'
        assert c.scalar(text('SELECT version_num FROM alembic_version'))=='0006_policy_control'


def test_policy_version_change_retains_guard_and_command_counter(postgres_db):
    from src.policy.models import command_counters
    engine=postgres_db.db.engine;setup(engine,elevated_profile='magma')
    for n in [1,2,3]:
        with engine.begin() as c:process(c,sig(n,'replay'),'test-v1',T+timedelta(seconds=n))
    with engine.begin() as c:
        install(c,'next',Rules(elevated_profile='unavailable').payload(),T,activate=True)
        d=process(c,sig(4,'security_violation'),'next',T+timedelta(seconds=4))
        assert d['observed_risk']=='CRITICAL'
        install(c,'test-v1',Rules(elevated_profile='magma').payload(),T,activate=True)
        d=process(c,sig(5),'test-v1',T+timedelta(seconds=5))
        assert d['observed_risk']=='CRITICAL'
        assert c.scalar(select(command_counters.c.last_sequence))==2
    with engine.connect() as c:assert c.scalar(select(states.c.applied).limit(1)) is None


def test_explicit_retention_preserves_identity_state_and_replay(postgres_db):
    from types import SimpleNamespace
    from src.policy.state import prune
    from src.policy.worker import prune_journal
    engine=postgres_db.db.engine;setup(engine)
    with engine.begin() as c:
        process(c,sig(1,'replay'),'test-v1',T+timedelta(seconds=1))
        c.execute(text("INSERT INTO mqtt_replay_state VALUES ('receiver','retention',1,77)"))
        capture(c,'accepted',SimpleNamespace(device_id='alpha',key_epoch=1,sequence_number=2),T)
    assert poll(engine)
    with engine.begin() as c:
        assert prune(c,1,T+timedelta(days=3))==1
        assert prune_journal(c,1,T+timedelta(days=3))==1
        assert c.scalar(select(queue.c.retained))==0
        assert process(c,sig(1,'replay'),'test-v1',T+timedelta(days=3)) is None
        assert c.scalar(select(states.c.device_id))=='alpha'
        assert c.scalar(text("SELECT last_sequence FROM mqtt_replay_state WHERE device_id='retention'"))==77
        assert c.scalar(select(signals.c.payload).where(signals.c.event_id=='test:1'))=={'retained_identity':True}
    with pytest.raises(ValueError):
        with engine.begin() as c:prune(c,True,T)

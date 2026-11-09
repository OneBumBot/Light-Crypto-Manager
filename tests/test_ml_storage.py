from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone,timedelta
import uuid
import pytest
from sqlalchemy import select,text,func
from src.ml_storage import publish_observation,feed,feed_state,events,models,model_status,claim_one,complete,prune_feed

pytestmark=pytest.mark.postgres


def manifest():
    return dict(model_id='unit-telemetry',model_version='1.0.0',artifact_sha256='a'*64,
        feature_version='telemetry-causal-v1',task='telemetry_anomaly',mode='DEMO')


def marker(engine,sequence=1):
    value=dict(id=str(uuid.uuid4()),device_id='raspb1',key_epoch=1,sequence_number=sequence)
    with engine.begin() as c:publish_observation(c,value,datetime.now(timezone.utc))
    return value


def test_marker_bounded_gap_does_not_block_delivery(postgres_db):
    engine=postgres_db.db.engine
    with engine.begin() as c:c.execute(feed_state.update().values(capacity=1))
    one=marker(engine)
    marker(engine,2)
    with engine.begin() as c:publish_observation(c,one,datetime.now(timezone.utc))
    with engine.connect() as c:
        state=c.execute(select(feed_state)).mappings().one()
        assert state['retained']==1 and state['overflow_skipped']==1 and state['published']==1
        assert c.scalar(select(func.count()).select_from(feed))==1


def test_claims_idempotent_fenced_and_model_versioned(postgres_db):
    engine=postgres_db.db.engine;model=manifest()
    assert model_status(engine,'unit-telemetry','1.0.0','available',model)
    for i in range(1,9):marker(engine,i)
    with ThreadPoolExecutor(max_workers=8) as pool:
        jobs=list(pool.map(lambda _:claim_one(engine,model),range(8)))
    assert len({job['id'] for job in jobs})==8
    assert claim_one(engine,model) is None
    old=jobs[0]
    with engine.begin() as c:c.execute(events.update().where(events.c.id==old['id']).values(lease_until=datetime.now(timezone.utc)-timedelta(seconds=1)))
    new=claim_one(engine,model)
    assert new['id']==old['id'] and new['claim_token']!=old['claim_token']
    assert not complete(engine,old,'ok',score=1,threshold=0.5,is_anomaly=True)
    assert complete(engine,new,'ok',score=1,threshold=0.5,is_anomaly=True)
    assert claim_one(engine,dict(model,model_version='2.0.0')) is not None
    assert not model_status(engine,'unit-telemetry','1.0.0','available',dict(model,artifact_sha256='b'*64))
    assert not model_status(engine,'unit-telemetry','1.0.0','available',dict(model,changed_threshold=3))


def test_retry_preserves_event_and_explicit_pruning(postgres_db):
    engine=postgres_db.db.engine;model=manifest();marker(engine)
    event=claim_one(engine,model)
    complete(engine,event,'retry',diagnostic='MongoUnavailable')
    with engine.begin() as c:
        c.execute(events.update().values(available_at=datetime.now(timezone.utc)-timedelta(seconds=1)))
    repeated=claim_one(engine,model)
    assert repeated['id']==event['id'] and repeated['attempts']==2
    complete(engine,repeated,'ok',score=0.4,threshold=0.8,is_anomaly=False)
    with engine.begin() as c:c.execute(feed.update().values(mongo_confirmed_at=datetime.now(timezone.utc)-timedelta(days=10)))
    assert prune_feed(engine,3)==1
    with engine.connect() as c:
        assert c.scalar(select(events.c.status))=='ok'
        assert c.scalar(select(events.c.observation_id)) is None
        assert c.scalar(select(feed_state.c.retained))==0


def test_signal_contract_does_not_choose_crypto(postgres_db):
    from src.ml_signals import signal
    value=dict(device_id='raspb1',key_epoch=1,sequence_number=7,detector='telemetry_anomaly',
        model_id='unit',model_version='1.0.0',feature_version='telemetry-causal-v1',status='ok',
        score=4.2,threshold=3.0,is_anomaly=True,evaluated_at=datetime.now(timezone.utc))
    output=signal(value,dict(mode='DEMO',score_semantics='robust deviations',score_upper_bound=None))
    assert output['trusted_detector'] is False
    assert output['score_range']==[0,None] and output['score_direction']=='higher_is_more_anomalous'
    assert not {'algorithm','crypto_profile','command','key'} & set(output)

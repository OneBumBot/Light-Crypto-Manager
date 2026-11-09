from datetime import datetime,timezone,timedelta
from pathlib import Path
import uuid
import pandas as pd
import pytest
from sqlalchemy import select,func
from src.ml_storage import feed,events,model_status,publish_observation
from src.classifier.ml.telemetry_features import causal_frame,build_telemetry
from src.classifier.ml.worker import evaluate_one
from src.mongo_repository import MongoRepository
from ml_fixtures import telemetry_rows

from test_mongo_storage import mongo

pytestmark=pytest.mark.postgres


def store_marked(web,repository,rows):
    for row in rows:
        repository.store(dict(row,crypto_profile='Ascon-AEAD128',sensors={}))
        with web.db.engine.begin() as c:
            publish_observation(c,dict(id=str(uuid.uuid4()),**{k:row[k] for k in ['device_id','key_epoch','sequence_number']}),datetime.now(timezone.utc))


def test_real_mongo_worker_restart_dedupe_causality_and_retry(postgres_db,mongo):
    device='ml_'+uuid.uuid4().hex[:16]
    rows=telemetry_rows(devices=(device,),count=16)
    frame,_=causal_frame(rows,5)
    pipeline=build_telemetry();pipeline.fit(frame.iloc[:7])
    manifest=dict(model_id='integration-model',model_version='1.0.0',task='telemetry_anomaly',
        feature_version='telemetry-causal-v1',artifact_sha256='a'*64,mode='DEMO',threshold=3.0,
        preprocessing=dict(window=5,expected_interval=10,score_range=[0,None],score_semantics='robust deviations'))
    model_status(postgres_db.db.engine,manifest['model_id'],manifest['model_version'],'available',manifest)
    store_marked(postgres_db,mongo,rows)
    while evaluate_one(postgres_db.db.engine,mongo,manifest,pipeline):pass
    expected=float(-pipeline.score_samples(frame.iloc[[-1]])[0])
    with postgres_db.db.engine.connect() as c:
        values=c.execute(select(events).order_by(events.c.sequence_number)).mappings().all()
        assert len(values)==16 and sum(v['status']=='ok' for v in values)==11
        assert values[-1]['score']==pytest.approx(expected)
    assert not evaluate_one(postgres_db.db.engine,mongo,manifest,pipeline)
    # New repository simulates consumer restart; PG evaluation identities remain authoritative.
    replacement=MongoRepository('history',password_file='/run/storage/history.password')
    try:assert not evaluate_one(postgres_db.db.engine,replacement,manifest,pipeline)
    finally:replacement.close()
    late=dict(rows[-1],sequence_number=17,measured_at=rows[0]['measured_at'])
    store_marked(postgres_db,mongo,[late])
    assert evaluate_one(postgres_db.db.engine,mongo,manifest,pipeline)
    with postgres_db.db.engine.connect() as c:
        assert c.scalar(select(events.c.status).where(events.c.sequence_number==17))=='out_of_order'
    later=dict(rows[-1],sequence_number=18)
    store_marked(postgres_db,mongo,[later])
    unavailable=MongoRepository('history',host='unreachable-mongo.invalid',password_file='/run/storage/history.password')
    try:assert evaluate_one(postgres_db.db.engine,unavailable,manifest,pipeline)
    finally:unavailable.close()
    with postgres_db.db.engine.connect() as c:
        assert c.scalar(select(events.c.status).where(events.c.sequence_number==18))=='retry'
        assert c.scalar(select(func.count()).select_from(events).where(events.c.status=='ok'))==11


def test_worker_cannot_score_network_model(postgres_db):
    with pytest.raises(ValueError,match='network IDS'):evaluate_one(postgres_db.db.engine,None,{'task':'network_ids'},None)

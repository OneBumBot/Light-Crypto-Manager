from datetime import datetime, timezone
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
import pytest
from pymongo.errors import OperationFailure
from sqlalchemy import select
from src.mongo_repository import MongoRepository, TelemetryConflict, document
from src.outbox_relay import deliver_one
from src.outbox import outbox
from test_outbox import ingest
from test_postgres import seed_device


def payload():
    return dict(device_id='test_'+uuid.uuid4().hex,key_epoch=1,sequence_number=1,
        measured_at=datetime.now(timezone.utc).isoformat(),received_at=datetime.now(timezone.utc).isoformat(),
        crypto_profile='Ascon-AEAD128',temperature=24.5,humidity=61.2,sensors={})


@pytest.fixture
def mongo():
    if os.environ.get('TEST_MONGO_ENABLED')!='1':
        pytest.skip('real authenticated test MongoDB required')
    repo=MongoRepository()
    yield repo
    repo.close()  # No delete permission. Isolated test project retains evidence.


def test_document_rejects_secrets_and_bad_types():
    data=payload()
    data['password']='public-test-value'
    with pytest.raises(ValueError): document(data)
    data=payload(); data['sequence_number']=True
    with pytest.raises(ValueError): document(data)
    data=payload(); data['sensors']={'unexpected':'value'}
    with pytest.raises(ValueError): document(data)


def test_real_mongo_idempotency_conflict_and_permissions(mongo):
    data=payload()
    assert mongo.store(data)
    assert mongo.store(data) is False
    changed=dict(data,temperature=99)
    with pytest.raises(TelemetryConflict): mongo.store(changed)
    assert len(mongo.history(device=data['device_id']))==1
    with pytest.raises(OperationFailure): mongo.collection.delete_one({'_id':document(data)['_id']})
    read=MongoRepository('history',password_file='/run/storage/history.password')
    try:
        assert read.history(device=data['device_id'])[0]['temperature']==24.5
        with pytest.raises(OperationFailure): read.store(payload())
    finally: read.close()


def test_parallel_mongo_inserts_are_idempotent(mongo):
    data=payload()
    with ThreadPoolExecutor(max_workers=8) as pool:
        results=list(pool.map(lambda _:mongo.store(data),range(8)))
    assert results.count(True)==1
    assert len(mongo.history(device=data['device_id']))==1


@pytest.mark.postgres
def test_crash_after_mongo_before_pg_ack(postgres_db,registry,mongo):
    # Unique provisioned test identity, same independently keyed registry entry.
    name='crash_'+uuid.uuid4().hex[:12]
    registry[name]=registry.pop('raspb1')
    registry[name]['topic']='iot/sensors/'+name
    seed_device(postgres_db)
    from src.telemetry import encode_packet
    from src.ingestion import process_packet
    packet=encode_packet(dict(temperature=65,humidity=50,timestamp=datetime.now(timezone.utc).isoformat()),registry,name,1)
    process_packet(packet,registry,postgres_db.db.engine,registry[name]['topic'])
    class Crash(BaseException): pass
    def crash(_): raise Crash()
    with pytest.raises(Crash): deliver_one(postgres_db.db.engine,mongo,after_write=crash,lease_seconds=0)
    assert len(mongo.history(device=name))==1
    assert deliver_one(postgres_db.db.engine,mongo)
    assert len(mongo.history(device=name))==1
    with postgres_db.db.engine.connect() as c:
        assert c.scalar(select(outbox.c.status))=='delivered'

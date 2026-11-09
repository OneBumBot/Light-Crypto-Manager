from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock
import pytest
from sqlalchemy import select, text, func
from src.ingestion import process_packet, IngestionBackpressure
from src.telemetry import encode_packet
from src.outbox import outbox, claim, finish, cleanup, requeue_dead
from src.outbox_relay import deliver_one
from src.replay import replay_state
from test_postgres import seed_device

pytestmark = pytest.mark.postgres


def ingest(web, registry, sequence=1):
    seed = dict(temperature=65, humidity=50, timestamp=datetime.now(timezone.utc).isoformat())
    packet=encode_packet(seed,registry,'raspb1',sequence)
    return process_packet(packet,registry,web.db.engine,'iot/sensors/raspb1')


def test_atomic_admission_and_replay(postgres_db,registry):
    web=postgres_db
    seed_device(web)
    ingest(web,registry)
    assert ingest(web,registry) is None
    with web.db.engine.connect() as c:
        assert c.scalar(select(func.count()).select_from(outbox))==1
        assert c.scalar(select(replay_state.c.last_sequence))==1
        assert c.scalar(text('SELECT count(*) FROM "Anomalies"'))==1


def test_outbox_insert_failure_rolls_back_all(postgres_db,registry):
    web=postgres_db
    seed_device(web)
    with web.db.engine.begin() as c:
        c.execute(text('ALTER TABLE telemetry_outbox ADD CONSTRAINT fail_insert CHECK (sequence_number < 0)'))
    with pytest.raises(Exception): ingest(web,registry)
    with web.db.engine.connect() as c:
        assert c.scalar(select(func.count()).select_from(replay_state))==0
        assert c.scalar(text('SELECT count(*) FROM "Anomalies"'))==0
        assert c.scalar(select(func.count()).select_from(outbox))==0


def test_claim_concurrency_and_fencing(postgres_db,registry):
    web=postgres_db
    seed_device(web)
    for i in range(1,9): ingest(web,registry,i)
    engine=web.db.engine
    with ThreadPoolExecutor(max_workers=8) as pool:
        events=list(pool.map(lambda _:claim(engine),range(8)))
    assert len({e['id'] for e in events})==8
    assert claim(web.db.engine) is None
    old=events[0]
    with web.db.engine.begin() as c:
        c.execute(outbox.update().where(outbox.c.id==old['id']).values(lease_until=datetime.now(timezone.utc)-timedelta(seconds=1)))
    new=claim(web.db.engine)
    assert new['id']==old['id'] and new['claim_token']!=old['claim_token']
    assert finish(web.db.engine,old) is False
    assert finish(web.db.engine,new) is True


def test_retry_dead_requeue_retention(postgres_db,registry):
    web=postgres_db
    seed_device(web)
    ingest(web,registry)
    for _ in range(2):
        event=claim(web.db.engine,max_attempts=2)
        finish(web.db.engine,event,RuntimeError('sensitive details'),max_attempts=2,backoff_base=0)
    assert claim(web.db.engine,max_attempts=2) is None
    with web.db.engine.connect() as c:
        row=c.execute(select(outbox)).mappings().one()
        assert row['status']=='dead' and row['last_error']=='RuntimeError'
    assert cleanup(web.db.engine,1)==0
    assert requeue_dead(web.db.engine,row['id'])==1
    finish(web.db.engine,claim(web.db.engine))
    assert cleanup(web.db.engine,0)==0
    with web.db.engine.begin() as c:
        c.execute(outbox.update().values(delivered_at=datetime.now(timezone.utc)-timedelta(days=3)))
    assert cleanup(web.db.engine,1)==1
    with web.db.engine.connect() as c:
        assert c.scalar(select(replay_state.c.last_sequence))==1


def test_backpressure_never_advances_replay(postgres_db,registry,monkeypatch):
    seed_device(postgres_db)
    monkeypatch.setenv('MAX_OUTBOX_PENDING','0')
    with pytest.raises(IngestionBackpressure): ingest(postgres_db,registry)
    with postgres_db.db.engine.connect() as c:
        assert c.scalar(select(func.count()).select_from(replay_state))==0


def test_relay_network_failure_retries(postgres_db,registry):
    seed_device(postgres_db)
    ingest(postgres_db,registry)
    repo=Mock()
    repo.store.side_effect=ConnectionError('private details')
    assert deliver_one(postgres_db.db.engine,repo,backoff_base=0)
    with postgres_db.db.engine.connect() as c:
        row=c.execute(select(outbox)).mappings().one()
        assert row['status']=='pending' and row['attempts']==1
    repo.store.side_effect=None
    assert deliver_one(postgres_db.db.engine,repo)
    with postgres_db.db.engine.connect() as c:
        assert c.scalar(select(outbox.c.status))=='delivered'

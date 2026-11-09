"""Durable telemetry journal. Claims are short PG transactions, never Mongo calls."""
from datetime import datetime, timedelta, timezone
import uuid
from sqlalchemy import (MetaData, Table, Column, String, BigInteger, Integer, DateTime,
                        CheckConstraint, UniqueConstraint, Index, select, update, delete, func, or_, and_)
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()
outbox = Table('telemetry_outbox', metadata,
    Column('id', String(36), primary_key=True),
    Column('device_id', String(48), nullable=False),
    Column('key_epoch', Integer, nullable=False),
    Column('sequence_number', BigInteger, nullable=False),
    Column('payload', JSONB, nullable=False),
    Column('created_at', DateTime(timezone=True), nullable=False),
    Column('status', String(12), nullable=False, server_default='pending'),
    Column('attempts', Integer, nullable=False, server_default='0'),
    Column('available_at', DateTime(timezone=True), nullable=False),
    Column('lease_until', DateTime(timezone=True)),
    Column('claim_token', String(36)),
    Column('delivered_at', DateTime(timezone=True)),
    Column('last_error', String(80)),
    UniqueConstraint('device_id','key_epoch','sequence_number', name='uq_outbox_identity'),
    CheckConstraint("status IN ('pending','claimed','delivered','dead')", name='ck_outbox_status'),
    CheckConstraint('attempts >= 0 AND key_epoch > 0 AND sequence_number > 0', name='ck_outbox_numbers'),
    CheckConstraint("jsonb_typeof(payload) = 'object' AND octet_length(payload::text) <= 8192", name='ck_outbox_payload'),
)
Index('ix_outbox_ready', outbox.c.status, outbox.c.available_at, outbox.c.lease_until)
Index('ix_outbox_retention', outbox.c.status, outbox.c.delivered_at)
metrics = Table('ingestion_metrics', metadata,
    Column('minute', DateTime(timezone=True), primary_key=True),
    Column('kind', String(20), primary_key=True),
    Column('count', BigInteger, nullable=False),
    CheckConstraint('count >= 0', name='ck_ingestion_count'))


def utcnow():
    return datetime.now(timezone.utc)


def record(connection, kind, now=None):
    from sqlalchemy.dialects.postgresql import insert
    minute = (now or utcnow()).replace(second=0, microsecond=0)
    stmt = insert(metrics).values(minute=minute, kind=kind, count=1)
    connection.execute(stmt.on_conflict_do_update(index_elements=['minute','kind'],
                       set_={'count': metrics.c.count + 1}))


def enqueue(connection, message, now):
    sensor = message.sensor
    payload = dict(device_id=message.device_id, key_epoch=message.key_epoch,
        sequence_number=message.sequence_number, crypto_profile='Ascon-AEAD128',
        measured_at=sensor['timestamp'], received_at=now.isoformat(),
        temperature=sensor['temperature'], humidity=sensor['humidity'], sensors={})
    connection.execute(outbox.insert().values(id=str(uuid.uuid4()), device_id=message.device_id,
        key_epoch=message.key_epoch, sequence_number=message.sequence_number,
        payload=payload, created_at=now, available_at=now))
    record(connection, 'accepted', now)


def claim(engine, *, lease_seconds=30, max_attempts=12):
    # Database clock avoids cross-worker wall-clock skew for leases.
    with engine.begin() as connection:
        now = connection.scalar(select(func.clock_timestamp()))
        ready = or_(and_(outbox.c.status == 'pending', outbox.c.available_at <= now),
                    and_(outbox.c.status == 'claimed', outbox.c.lease_until <= now))
        connection.execute(update(outbox).where(ready, outbox.c.attempts >= max_attempts)
            .values(status='dead', claim_token=None, lease_until=None, last_error='AttemptsExhausted'))
        row = connection.execute(select(outbox).where(ready, outbox.c.attempts < max_attempts)
            .order_by(outbox.c.available_at, outbox.c.id).with_for_update(skip_locked=True).limit(1)).mappings().first()
        if row is None:
            return None
        if row['attempts'] > 0:
            record(connection, 'delivery_retry', now)
        token = str(uuid.uuid4())
        result = connection.execute(update(outbox).where(outbox.c.id == row['id'])
            .values(status='claimed', attempts=outbox.c.attempts+1, claim_token=token,
                    lease_until=now+timedelta(seconds=lease_seconds)).returning(outbox)).mappings().one()
        return dict(result)


def finish(engine, event, error=None, *, max_attempts=12, backoff_base=1, backoff_cap=300):
    with engine.begin() as connection:
        now = connection.scalar(select(func.clock_timestamp()))
        where = and_(outbox.c.id == event['id'], outbox.c.status == 'claimed',
                     outbox.c.claim_token == event['claim_token'])
        if error is None:
            values = dict(status='delivered', delivered_at=now, last_error=None)
        else:
            values = dict(status='dead' if event['attempts'] >= max_attempts else 'pending',
                          available_at=now+timedelta(seconds=min(backoff_cap,backoff_base*2**min(event['attempts']-1,20))),
                          last_error=type(error).__name__[:80])
        result = connection.execute(update(outbox).where(where).values(**values, claim_token=None,lease_until=None))
        if result.rowcount and error is None:
            from src.ml_storage import publish_observation
            publish_observation(connection,event,now)
        if result.rowcount:
            record(connection, 'delivered' if error is None else 'delivery_error')
        return bool(result.rowcount)


def cleanup(engine, days, batch=1000):
    if days <= 0:
        return 0  # Disabled unless explicitly configured.
    with engine.begin() as connection:
        cutoff = connection.scalar(select(func.clock_timestamp()))-timedelta(days=days)
        ids = select(outbox.c.id).where(outbox.c.status=='delivered', outbox.c.delivered_at < cutoff).limit(batch)
        return connection.execute(delete(outbox).where(outbox.c.id.in_(ids))).rowcount


def requeue_dead(engine, event_id):
    with engine.begin() as connection:
        return connection.execute(update(outbox).where(outbox.c.id==event_id, outbox.c.status=='dead')
            .values(status='pending', attempts=0, available_at=func.clock_timestamp(), last_error=None)).rowcount

"""Lightweight ML journal/event storage. No sklearn import on the telemetry path."""
from datetime import timedelta
import uuid
import hashlib
import json
from sqlalchemy import (MetaData,Table,Column,String,Integer,BigInteger,Float,Boolean,DateTime,
    ForeignKey,UniqueConstraint,CheckConstraint,Index,select,update,func,and_,or_,text)
from sqlalchemy.dialects.postgresql import insert

metadata=MetaData()
feed=Table('ml_observations',metadata,
    Column('id',String(36),primary_key=True),Column('device_id',String(48),nullable=False),
    Column('key_epoch',Integer,nullable=False),Column('sequence_number',BigInteger,nullable=False),
    Column('mongo_confirmed_at',DateTime(timezone=True),nullable=False),
    UniqueConstraint('device_id','key_epoch','sequence_number',name='uq_ml_observation'),
    CheckConstraint('key_epoch>0 AND sequence_number>0',name='ck_ml_observation_numbers'))
Index('ix_ml_feed_order',feed.c.mongo_confirmed_at,feed.c.id)
feed_state=Table('ml_feed_state',metadata,
    Column('id',Integer,primary_key=True),Column('capacity',Integer,nullable=False,server_default='100000'),
    Column('retained',BigInteger,nullable=False,server_default='0'),
    Column('published',BigInteger,nullable=False,server_default='0'),
    Column('overflow_skipped',BigInteger,nullable=False,server_default='0'),
    Column('pruned',BigInteger,nullable=False,server_default='0'),
    Column('last_gap_at',DateTime(timezone=True)),
    CheckConstraint('id=1 AND capacity>0 AND retained>=0 AND published>=0 AND overflow_skipped>=0 AND pruned>=0',name='ck_ml_feed_state'))
models=Table('ml_models',metadata,
    Column('model_id',String(48),primary_key=True),Column('model_version',String(48),primary_key=True),
    Column('artifact_sha256',String(64)),Column('manifest_sha256',String(64)),Column('feature_version',String(40)),
    Column('detector',String(32),nullable=False,server_default='telemetry_anomaly'),
    Column('mode',String(16),nullable=False,server_default='DEMO'),
    Column('score_semantics',String(256)),Column('score_upper_bound',Float),
    Column('status',String(24),nullable=False),Column('heartbeat_at',DateTime(timezone=True),nullable=False),
    Column('diagnostic',String(80)),
    CheckConstraint("status IN ('available','unavailable','disabled','version_conflict')",name='ck_ml_model_status'))
events=Table('ml_anomaly_events',metadata,
    Column('id',String(36),primary_key=True),
    Column('observation_id',String(36),ForeignKey('ml_observations.id',ondelete='SET NULL')),
    Column('device_id',String(48),nullable=False),Column('key_epoch',Integer,nullable=False),
    Column('sequence_number',BigInteger,nullable=False),Column('model_id',String(48),nullable=False),
    Column('model_version',String(48),nullable=False),Column('feature_version',String(40),nullable=False),
    Column('detector',String(32),nullable=False,server_default='telemetry_anomaly'),
    Column('status',String(24),nullable=False),Column('diagnostic',String(80)),
    Column('score',Float),Column('threshold',Float),Column('is_anomaly',Boolean),
    Column('evaluated_at',DateTime(timezone=True)),Column('prepare_ms',Float),Column('inference_ms',Float),
    Column('delivery_ack_lag_seconds',Float),Column('attempts',Integer,nullable=False,server_default='0'),
    Column('available_at',DateTime(timezone=True),nullable=False),
    Column('claim_token',String(36)),Column('lease_until',DateTime(timezone=True)),
    UniqueConstraint('device_id','key_epoch','sequence_number','model_id','model_version',name='uq_ml_evaluation_identity'),
    CheckConstraint('key_epoch>0 AND sequence_number>0 AND attempts>=0',name='ck_ml_event_numbers'),
    CheckConstraint("status IN ('processing','retry','ok','warmup','unknown_device','out_of_order','invalid_history','dead','feed_expired')",name='ck_ml_event_status'),
    CheckConstraint("status!='ok' OR (score IS NOT NULL AND threshold IS NOT NULL AND is_anomaly IS NOT NULL AND evaluated_at IS NOT NULL)",name='ck_ml_scored_event'),
    CheckConstraint("score IS NULL OR (score>=0 AND score<'Infinity'::float8)",name='ck_ml_finite_score'),
    CheckConstraint("threshold IS NULL OR (threshold>=0 AND threshold<'Infinity'::float8)",name='ck_ml_finite_threshold'))
Index('ix_ml_event_claim',events.c.model_id,events.c.model_version,events.c.status,events.c.available_at)
Index('ix_ml_event_history',events.c.device_id,events.c.evaluated_at)


def publish_observation(connection,event,now):
    # Bounded durable feed, independent of loaded models. Overflow is explicit.
    connection.execute(insert(feed_state).values(id=1).on_conflict_do_nothing())
    state=connection.execute(select(feed_state).where(feed_state.c.id==1).with_for_update()).mappings().one()
    if connection.scalar(select(feed.c.id).where(feed.c.id==event['id'])): return
    if state['retained']>=state['capacity']:
        connection.execute(update(feed_state).where(feed_state.c.id==1).values(
            overflow_skipped=feed_state.c.overflow_skipped+1,last_gap_at=now))
        return
    connection.execute(feed.insert().values(id=event['id'],device_id=event['device_id'],
        key_epoch=event['key_epoch'],sequence_number=event['sequence_number'],mongo_confirmed_at=now))
    connection.execute(update(feed_state).where(feed_state.c.id==1).values(
        retained=feed_state.c.retained+1,published=feed_state.c.published+1))


def model_status(engine,model_id,version,status,manifest=None,diagnostic=None):
    with engine.begin() as c:
        now=c.scalar(select(func.clock_timestamp()))
        c.execute(insert(models).values(model_id=model_id,model_version=version,status=status,heartbeat_at=now)
                  .on_conflict_do_nothing())
        old=c.execute(select(models).where(models.c.model_id==model_id,models.c.model_version==version).with_for_update()).mappings().one()
        values=dict(status=status,heartbeat_at=now,diagnostic=diagnostic)
        if manifest:
            digest=manifest['artifact_sha256']
            manifest_digest=hashlib.sha256(json.dumps(manifest,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
            if old['artifact_sha256'] and (old['artifact_sha256']!=digest or old['manifest_sha256']!=manifest_digest):
                c.execute(update(models).where(models.c.model_id==model_id,models.c.model_version==version)
                    .values(status='version_conflict',heartbeat_at=now,diagnostic='ImmutableVersionConflict'))
                return False
            values.update(artifact_sha256=digest,manifest_sha256=manifest_digest,feature_version=manifest['feature_version'],mode=manifest['mode'],
                score_semantics=manifest.get('preprocessing',{}).get('score_semantics','model-specific higher-is-more-anomalous research score'),
                score_upper_bound=manifest.get('preprocessing',{}).get('score_range',[0,None])[1])
        c.execute(update(models).where(models.c.model_id==model_id,models.c.model_version==version).values(**values))
        return True


def claim_one(engine,manifest,lease_seconds=30,max_attempts=8):
    mid=manifest['model_id'];version=manifest['model_version']
    with engine.begin() as c:
        now=c.scalar(select(func.clock_timestamp()))
        join=feed.outerjoin(events,and_(events.c.observation_id==feed.c.id,events.c.model_id==mid,events.c.model_version==version))
        ready=or_(events.c.id.is_(None),and_(events.c.status=='retry',events.c.available_at<=now),
                  and_(events.c.status=='processing',events.c.lease_until<=now))
        row=c.execute(select(feed,events.c.id.label('event_id'),events.c.attempts)
            .select_from(join).where(ready).order_by(feed.c.mongo_confirmed_at,feed.c.id)
            .with_for_update(of=feed,skip_locked=True).limit(1)).mappings().first()
        if row is None:return None
        token=str(uuid.uuid4());event_id=row['event_id'] or str(uuid.uuid4())
        if row['event_id'] and row['attempts']>=max_attempts:
            c.execute(update(events).where(events.c.id==event_id).values(status='dead',diagnostic='AttemptsExhausted',
                claim_token=None,lease_until=None,evaluated_at=now))
            return None
        values=dict(observation_id=row['id'],device_id=row['device_id'],key_epoch=row['key_epoch'],
            sequence_number=row['sequence_number'],model_id=mid,model_version=version,feature_version=manifest['feature_version'],
            status='processing',attempts=(row['attempts'] or 0)+1,available_at=now,
            claim_token=token,lease_until=now+timedelta(seconds=lease_seconds))
        if row['event_id']:c.execute(update(events).where(events.c.id==event_id).values(**values))
        else:c.execute(events.insert().values(id=event_id,**values))
        return dict(id=event_id,**values,mongo_confirmed_at=row['mongo_confirmed_at'])


def complete(engine,event,status,*,score=None,threshold=None,is_anomaly=None,diagnostic=None,prepare_ms=0,inference_ms=0):
    with engine.begin() as c:
        now=c.scalar(select(func.clock_timestamp()))
        values=dict(status=status,score=score,threshold=threshold,is_anomaly=is_anomaly,diagnostic=diagnostic,
            prepare_ms=prepare_ms,inference_ms=inference_ms,evaluated_at=now,claim_token=None,lease_until=None,
            delivery_ack_lag_seconds=max(0,(now-event['mongo_confirmed_at']).total_seconds()))
        if status=='retry':values['available_at']=now+timedelta(seconds=min(300,2**min(event['attempts'],8)))
        return c.execute(update(events).where(events.c.id==event['id'],events.c.claim_token==event['claim_token'],
            events.c.status=='processing').values(**values)).rowcount==1


def prune_feed(engine,days):
    if type(days) is not int or days<=0:raise ValueError('Explicit positive retention days required')
    with engine.begin() as c:
        c.execute(select(feed_state).where(feed_state.c.id==1).with_for_update())
        now=c.scalar(select(func.clock_timestamp()))
        ids=list(c.scalars(select(feed.c.id).where(feed.c.mongo_confirmed_at<now-timedelta(days=days)).limit(1000)))
        if not ids:return 0
        c.execute(update(events).where(events.c.observation_id.in_(ids),events.c.status.in_(['processing','retry']))
            .values(status='feed_expired',claim_token=None,lease_until=None,diagnostic='ExplicitFeedRetention',evaluated_at=now))
        c.execute(feed.delete().where(feed.c.id.in_(ids)))
        c.execute(update(feed_state).where(feed_state.c.id==1).values(retained=feed_state.c.retained-len(ids),
            pruned=feed_state.c.pruned+len(ids),last_gap_at=now))
        return len(ids)

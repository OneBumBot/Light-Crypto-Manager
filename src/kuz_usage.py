"""Conservative per-key MGM budget. No key bytes in SQL.

Every issued 10000-sequence range burns 10000 potential MGM invocations,
including ranges issued while another AEAD is active. No refund after crashes.
Authentication attempts burn a separate durable allowance before verification.
"""
from sqlalchemy import MetaData,Table,Column,String,BigInteger,Integer,DateTime,CheckConstraint,select,update,func
from src.crypto_profiles import KUZ
from src.telemetry import InvalidTelemetry

MAX_INVOCATIONS=2**20
BLOCKS_PER_INVOCATION=320
MAX_VERIFY_ATTEMPTS=2**20
DOMAIN=b'LCM\x01'
metadata=MetaData()
usage=Table('crypto_key_usage',metadata,
    Column('device_id',String(48),primary_key=True),Column('key_epoch',Integer,primary_key=True),
    Column('profile_id',String(64),primary_key=True),Column('key_reference',String(96),nullable=False),
    Column('nonce_policy',String(48),nullable=False),
    Column('reserved_invocations',BigInteger,nullable=False),Column('reserved_blocks',BigInteger,nullable=False),
    Column('max_invocations',BigInteger,nullable=False),Column('max_blocks',BigInteger,nullable=False),
    Column('verify_attempts',BigInteger,nullable=False),Column('max_verify_attempts',BigInteger,nullable=False),
    Column('created_at',DateTime(timezone=True),nullable=False),Column('updated_at',DateTime(timezone=True),nullable=False),
    CheckConstraint('reserved_invocations>=0 AND reserved_invocations<=max_invocations AND max_invocations<=1048576 AND reserved_blocks=320*reserved_invocations AND reserved_blocks<=max_blocks AND max_blocks<=335544320 AND verify_attempts>=0 AND verify_attempts<=max_verify_attempts AND max_verify_attempts<=1048576',name='ck_mgm_budget'))
reservations=Table('crypto_usage_reservations',metadata,
    Column('request_id',String(36),primary_key=True),Column('device_id',String(48),nullable=False),
    Column('key_epoch',Integer,nullable=False),Column('profile_id',String(64),nullable=False),
    Column('first_sequence',BigInteger,nullable=False),Column('last_sequence',BigInteger,nullable=False),
    Column('invocations',BigInteger,nullable=False),Column('blocks',BigInteger,nullable=False),
    Column('created_at',DateTime(timezone=True),nullable=False),
    CheckConstraint('first_sequence>0 AND last_sequence>=first_sequence AND invocations=last_sequence-first_sequence+1 AND blocks=320*invocations',name='ck_mgm_reservation'))


def nonce(epoch,sequence):
    if type(epoch) is not int or not 1<=epoch<2**31 or type(sequence) is not int or not 1<=sequence<=2**63-1:
        raise ValueError('Invalid MGM nonce coordinates')
    return epoch.to_bytes(4,'big')+sequence.to_bytes(8,'big')+DOMAIN


def initialize_fresh(c,device,epoch):
    """Only called on a newly inserted provisioned device; no historical backfill."""
    c.execute(usage.insert().values(device_id=device,key_epoch=epoch,profile_id=KUZ,key_reference=KUZ+':'+str(epoch),
        nonce_policy='epoch31-sequence64-LCM01',reserved_invocations=0,reserved_blocks=0,
        max_invocations=MAX_INVOCATIONS,max_blocks=MAX_INVOCATIONS*BLOCKS_PER_INVOCATION,
        verify_attempts=0,max_verify_attempts=MAX_VERIFY_ATTEMPTS,created_at=func.clock_timestamp(),updated_at=func.clock_timestamp()))


def locked(c,device,epoch):
    row=c.execute(select(usage).where(usage.c.device_id==device,usage.c.key_epoch==epoch,usage.c.profile_id==KUZ).with_for_update()).mappings().first()
    if row is None:raise ValueError('MGM usage authority missing; reviewed rekey required')
    if row['key_reference']!=KUZ+':'+str(epoch) or row['nonce_policy']!='epoch31-sequence64-LCM01':raise ValueError('MGM usage binding mismatch')
    totals=c.execute(select(func.coalesce(func.sum(reservations.c.invocations),0),func.coalesce(func.max(reservations.c.last_sequence),0)).where(reservations.c.device_id==device,reservations.c.key_epoch==epoch,reservations.c.profile_id==KUZ)).one()
    if totals[0]!=row['reserved_invocations']:raise ValueError('MGM accounting mismatch; reviewed rekey required')
    return row,totals[1]


def reserve(c,device,epoch,request_id,first,last):
    row,high=locked(c,device,epoch)
    count=last-first+1
    if first<=high or count<=0:raise ValueError('MGM range reuse rejected')
    if row['reserved_invocations']+count>row['max_invocations'] or row['reserved_blocks']+320*count>row['max_blocks']:
        raise ValueError('MGM budget exhausted; reviewed rekey required')
    c.execute(reservations.insert().values(request_id=request_id,device_id=device,key_epoch=epoch,profile_id=KUZ,first_sequence=first,last_sequence=last,invocations=count,blocks=320*count,created_at=func.clock_timestamp()))
    c.execute(update(usage).where(usage.c.device_id==device,usage.c.key_epoch==epoch,usage.c.profile_id==KUZ).values(reserved_invocations=row['reserved_invocations']+count,reserved_blocks=row['reserved_blocks']+320*count,updated_at=func.clock_timestamp()))


def verify_attempt(engine,device,epoch,sequence):
    # Independent commit: tag failure and outer transaction rollback do not refund.
    # Infrastructure errors propagate; receiver must retain its redelivery semantics.
    with engine.begin() as c:
        try:row,_=locked(c,device,epoch)
        except ValueError:raise InvalidTelemetry('MGM usage authority unavailable') from None
        if row['verify_attempts']>=row['max_verify_attempts']:raise InvalidTelemetry('MGM verification budget exhausted')
        allowed=c.scalar(select(reservations.c.request_id).where(reservations.c.device_id==device,reservations.c.key_epoch==epoch,
            reservations.c.first_sequence<=sequence,reservations.c.last_sequence>=sequence).limit(1))
        if not allowed:raise InvalidTelemetry('MGM sequence not reserved')
        c.execute(update(usage).where(usage.c.device_id==device,usage.c.key_epoch==epoch,usage.c.profile_id==KUZ).values(verify_attempts=row['verify_attempts']+1,updated_at=func.clock_timestamp()))

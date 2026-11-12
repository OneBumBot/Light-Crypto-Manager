"""Policy persistence separate from telemetry keys, replay state and legacy ORM."""
from sqlalchemy import (MetaData,Table,Column,String,Integer,Boolean,DateTime,Float,BigInteger,
                        CheckConstraint,UniqueConstraint,ForeignKey,Index,text)
from sqlalchemy.dialects.postgresql import JSONB

metadata=MetaData()
versions=Table('policy_versions',metadata,
    Column('version',String(64),primary_key=True),Column('config',JSONB,nullable=False),Column('sha256',String(64),nullable=False),
    Column('active',Boolean,nullable=False,server_default='false'),Column('created_at',DateTime(timezone=True),nullable=False))
Index('uq_policy_active',versions.c.active,unique=True,postgresql_where=versions.c.active.is_(True))
states=Table('policy_device_states',metadata,
    Column('device_id',String(48),primary_key=True),Column('version',String(64),ForeignKey('policy_versions.version'),primary_key=True),
    Column('state',JSONB,nullable=False),Column('observed_risk',String(16),nullable=False),
    Column('recommended',JSONB),Column('requested',JSONB),Column('applied',JSONB),
    Column('effective_security_state',String(32),nullable=False,server_default='unconfirmed'),
    Column('configured_profile',String(64),nullable=False,server_default='ascon-aead128-v1'),
    Column('revision',BigInteger,nullable=False,server_default='0'),Column('updated_at',DateTime(timezone=True),nullable=False),
    CheckConstraint("observed_risk IN ('NORMAL','WATCH','ALERT','CRITICAL','UNKNOWN')",name='ck_policy_risk'),
    CheckConstraint("applied IS NULL AND effective_security_state='unconfirmed'",name='ck_policy_no_live_ack'))
signals=Table('policy_signals',metadata,
    Column('event_id',String(160),primary_key=True),Column('version',String(64),ForeignKey('policy_versions.version'),primary_key=True),
    Column('device_id',String(48)),Column('source',String(16),nullable=False),Column('payload',JSONB,nullable=False),
    Column('status',String(24),nullable=False),Column('created_at',DateTime(timezone=True),nullable=False))
Index('ix_policy_signal_history',signals.c.device_id,signals.c.created_at)
decisions=Table('policy_decisions',metadata,
    Column('id',String(36),primary_key=True),Column('event_id',String(160),nullable=False),
    Column('version',String(64),ForeignKey('policy_versions.version'),nullable=False),Column('device_id',String(48)),
    Column('result',JSONB,nullable=False),Column('created_at',DateTime(timezone=True),nullable=False),
    Column('compute_ms',Float,nullable=False),Column('source_lag_seconds',Float,nullable=False),
    UniqueConstraint('event_id','version',name='uq_policy_decision_event'))
Index('ix_policy_decision_history',decisions.c.created_at,decisions.c.id)
transitions=Table('policy_transitions',metadata,
    Column('id',String(36),primary_key=True),Column('decision_id',String(36),ForeignKey('policy_decisions.id'),nullable=False,unique=True),
    Column('device_id',String(48),nullable=False),Column('version',String(64),nullable=False),
    Column('from_state',String(16),nullable=False),Column('to_state',String(16),nullable=False),
    Column('at',DateTime(timezone=True),nullable=False))
intents=Table('policy_control_intents',metadata,
    Column('id',String(36),primary_key=True),Column('decision_id',String(36),ForeignKey('policy_decisions.id'),nullable=False,unique=True),
    Column('device_id',String(48),nullable=False),Column('command',JSONB,nullable=False),
    Column('status',String(24),nullable=False),Column('created_at',DateTime(timezone=True),nullable=False),
    CheckConstraint("status IN ('proposed','unsupported','expired','failed','simulated')",name='ck_policy_intent_status'))
worker_status=Table('policy_worker_status',metadata,
    Column('worker_id',String(64),primary_key=True),Column('status',String(24),nullable=False),
    Column('mode',String(16),nullable=False),Column('heartbeat_at',DateTime(timezone=True),nullable=False),
    Column('diagnostic',String(80)),Column('metrics',JSONB,nullable=False,server_default='{}'))
pending=Table('policy_pending',metadata,
    Column('event_id',String(160),primary_key=True),Column('kind',String(16),nullable=False),
    Column('source_id',String(36),nullable=False),Column('sort_at',DateTime(timezone=True),nullable=False),
    Column('payload',JSONB,nullable=False),
    CheckConstraint("kind IN ('security','ml')",name='ck_policy_pending_kind'))
Index('ix_policy_pending_order',pending.c.kind,pending.c.sort_at,pending.c.event_id)
schedule=Table('policy_schedule',metadata,Column('id',Integer,primary_key=True),
    Column('next_ml',Boolean,nullable=False,server_default='false'),CheckConstraint('id=1',name='ck_policy_schedule'))
Index('ix_policy_signal_processed',signals.c.version,signals.c.created_at)
audit=Table('policy_admin_audit',metadata,
    Column('id',String(36),primary_key=True),Column('actor',String(64),nullable=False),
    Column('action',String(32),nullable=False),Column('version',String(64),nullable=False),
    Column('at',DateTime(timezone=True),nullable=False))
command_counters=Table('policy_control_counters',metadata,
    Column('device_id',String(48),primary_key=True),Column('command_epoch',BigInteger,nullable=False,server_default='1'),
    Column('last_sequence',BigInteger,nullable=False,server_default='0'),
    CheckConstraint('command_epoch>0 AND last_sequence>=0',name='ck_policy_command_counter'))

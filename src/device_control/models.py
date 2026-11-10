"""Additive PG live control authority; keys remain outside PG."""
from sqlalchemy import MetaData,Table,Column,String,BigInteger,Integer,DateTime,Boolean,UniqueConstraint,CheckConstraint,Index,ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
metadata=MetaData()
D=lambda name:Column(name,DateTime(timezone=True))
devices=Table('live_control_devices',metadata,
    Column('device_id',String(48),primary_key=True),Column('key_epoch',Integer,nullable=False),
    Column('capabilities',JSONB,nullable=False),Column('key_fingerprint',String(64),nullable=False),
    Column('sequence_reserved',BigInteger,nullable=False,server_default='0'),
    Column('command_sequence',BigInteger,nullable=False,server_default='0'),
    Column('command_acknowledged',BigInteger,nullable=False,server_default='0'),
    Column('effective_profile',String(64)),Column('reported_profile',String(64)),
    Column('effective_event',String(36)),Column('pending_transition',String(36)),
    D('effective_at'),D('last_request_at'),
    CheckConstraint('key_epoch>0 AND sequence_reserved>=0 AND sequence_reserved<=4294967295 AND command_sequence>=0 AND command_acknowledged>=0',name='ck_live_counter'))
transitions=Table('live_control_transitions',metadata,
    Column('id',String(36),primary_key=True),Column('device_id',String(48),ForeignKey('live_control_devices.device_id'),nullable=False),
    Column('old_profile',String(64),nullable=False),Column('target_profile',String(64),nullable=False),
    Column('phase',String(32),nullable=False),Column('actor',String(64),nullable=False),
    Column('correlation_id',String(36),nullable=False,unique=True),D('created_at'),D('deadline'),D('activated_at'),D('acknowledged_at'),D('confirmed_at'),
    Column('telemetry_event',String(36)),Column('error',String(64)))
commands=Table('live_control_commands',metadata,
    Column('id',String(36),primary_key=True),Column('transition_id',String(36),ForeignKey('live_control_transitions.id'),nullable=False),
    Column('device_id',String(48),nullable=False),Column('command_epoch',Integer,nullable=False),
    Column('sequence',BigInteger,nullable=False),Column('phase',String(16),nullable=False),Column('body',JSONB,nullable=False),
    Column('wire',String(8192)),Column('status',String(16),nullable=False,server_default='pending'),
    Column('attempts',Integer,nullable=False,server_default='0'),D('available_at'),D('lease_until'),Column('claim',String(36)),D('expires_at'),
    UniqueConstraint('device_id','command_epoch','sequence',name='uq_live_command_sequence'),UniqueConstraint('transition_id','phase',name='uq_live_transition_phase'))
acks=Table('live_control_acks',metadata,
    Column('id',String(36),primary_key=True),Column('command_id',String(36),ForeignKey('live_control_commands.id'),nullable=False,unique=True),
    Column('device_id',String(48),nullable=False),Column('body',JSONB,nullable=False),Column('sha256',String(64),nullable=False),D('received_at'))
leases=Table('live_control_leases',metadata,
    Column('request_id',String(36),primary_key=True),Column('device_id',String(48),nullable=False),
    Column('boot_id',String(36),nullable=False),Column('body',JSONB,nullable=False),D('created_at'),
    UniqueConstraint('device_id','boot_id',name='uq_live_boot_lease'))
audit=Table('live_control_audit',metadata,
    Column('id',String(36),primary_key=True),Column('device_id',String(48),nullable=False),Column('transition_id',String(36)),
    Column('action',String(48),nullable=False),Column('detail',JSONB,nullable=False),D('at'))
workers=Table('live_control_workers',metadata,Column('id',String(64),primary_key=True),D('heartbeat'),Column('status',String(24),nullable=False))
Index('ix_live_command_delivery',commands.c.status,commands.c.available_at)
Index('ix_live_control_history',audit.c.device_id,audit.c.at)
# Small immutable receipts only at baseline/switch confirmation, not a second telemetry history.
evidence=Table('live_control_evidence',metadata,
    Column('event_id',String(36),primary_key=True),Column('device_id',String(48),nullable=False),
    Column('key_epoch',Integer,nullable=False),Column('sequence_number',BigInteger,nullable=False),
    Column('profile',String(64),nullable=False),Column('packet_sha256',String(64),nullable=False),
    Column('key_reference',String(96),nullable=False),Column('accepted_at',DateTime(timezone=True),nullable=False),
    UniqueConstraint('device_id','key_epoch','sequence_number',name='uq_live_evidence_identity'))

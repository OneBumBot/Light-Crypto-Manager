"""Bounded ingestion provenance journal; independent of Policy Worker availability."""
from datetime import datetime,timezone
import uuid
from sqlalchemy import MetaData,Table,Column,String,Integer,BigInteger,DateTime,CheckConstraint,select,update,Index
from sqlalchemy.dialects.postgresql import insert

metadata=MetaData()
journal=Table('security_observations',metadata,
    Column('id',String(36),primary_key=True),Column('source',String(16),nullable=False),
    Column('category',String(32),nullable=False),Column('device_id',String(48)),
    Column('key_epoch',Integer),Column('sequence_number',BigInteger),
    Column('occurred_at',DateTime(timezone=True),nullable=False),
    CheckConstraint("source IN ('protocol','rule')",name='ck_security_source'),
    CheckConstraint("category IN ('accepted','replay','rejected','physical_anomaly','delivery_delay')",name='ck_security_category'),
    CheckConstraint("(category='rejected' AND device_id IS NULL AND key_epoch IS NULL AND sequence_number IS NULL) OR (category!='rejected' AND device_id IS NOT NULL AND key_epoch>0 AND sequence_number>0)",name='ck_security_binding'))
Index('ix_security_observation_order',journal.c.occurred_at,journal.c.id)
queue=Table('security_observation_capacity',metadata,
    Column('id',Integer,primary_key=True),Column('capacity',Integer,nullable=False,server_default='100000'),
    Column('retained',BigInteger,nullable=False,server_default='0'),Column('overflow',BigInteger,nullable=False,server_default='0'),
    CheckConstraint('id=1 AND capacity>0 AND retained>=0 AND overflow>=0',name='ck_security_capacity'))


def capture(connection,category,message=None,now=None):
    if category not in {'accepted','replay','rejected','physical_anomaly','delivery_delay'}:raise ValueError('Unknown observation')
    if (category=='rejected') != (message is None):raise ValueError('Rejects cannot assert device identity')
    connection.execute(insert(queue).values(id=1).on_conflict_do_nothing())
    state=connection.execute(select(queue).where(queue.c.id==1).with_for_update()).mappings().one()
    if state['retained']>=state['capacity']:
        connection.execute(update(queue).where(queue.c.id==1).values(overflow=queue.c.overflow+1));return None
    identity={} if message is None else {k:getattr(message,k) for k in ['device_id','key_epoch','sequence_number']}
    event_id=str(uuid.uuid4())
    connection.execute(journal.insert().values(id=event_id,source='rule' if category in {'physical_anomaly','delivery_delay'} else 'protocol',
        category=category,occurred_at=now or datetime.now(timezone.utc),**identity))
    connection.execute(update(queue).where(queue.c.id==1).values(retained=queue.c.retained+1))
    return event_id

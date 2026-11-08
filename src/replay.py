"""PostgreSQL replay admission; caller includes all DB effects in this transaction."""
from sqlalchemy import BigInteger, Column, Integer, MetaData, String, Table, CheckConstraint
from sqlalchemy.dialects.postgresql import insert

metadata=MetaData()
replay_state=Table('mqtt_replay_state',metadata,
    Column('consumer',String(16),primary_key=True),
    Column('device_id',String(48),primary_key=True),
    Column('key_epoch',Integer,primary_key=True),
    Column('last_sequence',BigInteger,nullable=False),
    CheckConstraint('last_sequence > 0 AND key_epoch > 0'))


def admit(connection, message, consumer):
    if consumer not in ['receiver','web']: raise ValueError('Unknown consumer')
    stmt=insert(replay_state).values(consumer=consumer,device_id=message.device_id,
                                    key_epoch=message.key_epoch,last_sequence=message.sequence_number)
    stmt=stmt.on_conflict_do_update(
        index_elements=['consumer','device_id','key_epoch'],
        set_={'last_sequence':stmt.excluded.last_sequence},
        where=replay_state.c.last_sequence < stmt.excluded.last_sequence,
    ).returning(replay_state.c.last_sequence)
    return connection.execute(stmt).first() is not None

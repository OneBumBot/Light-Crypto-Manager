"""Additive 0007→0008 upgrade preserves actual control/replay rows, no backfill fiction."""
import uuid
from datetime import datetime,timezone,timedelta
import pytest
from sqlalchemy import select,text
from alembic.config import Config
from alembic import command
from src.device_control import models as m,server
from src.crypto_profiles import ASCON,AES
from src.migrate import upgrade

pytestmark=pytest.mark.postgres


def test_control_upgrade_preserves_pending_command_and_counter(legacy_postgres_db):
    engine=legacy_postgres_db.db.engine;tid=str(uuid.uuid4());now=datetime.now(timezone.utc)
    with engine.begin() as c:
        config=Config('alembic.ini');config.attributes['connection']=c;command.upgrade(config,'0007_live_control')
        c.execute(m.devices.insert().values(device_id='migration-control',key_epoch=1,capabilities=[ASCON,AES],key_fingerprint='0'*64,sequence_reserved=10000,effective_profile=ASCON,pending_transition=tid))
        t=dict(id=tid,device_id='migration-control',old_profile=ASCON,target_profile=AES,phase='ACTIVATION_SENT',actor='admin:fixture',correlation_id=str(uuid.uuid4()),created_at=now,deadline=now+timedelta(seconds=120))
        c.execute(m.transitions.insert().values(**t))
        d=c.execute(select(m.devices)).mappings().one();server.add_command(c,d,t,'ACTIVATE')
        c.execute(text("INSERT INTO mqtt_replay_state VALUES ('receiver','migration-control',1,123)"))
        before=dict(c.execute(select(m.commands)).mappings().one())
    upgrade(engine);upgrade(engine)
    with engine.connect() as c:
        assert dict(c.execute(select(m.commands)).mappings().one())==before
        assert c.scalar(select(m.devices.c.sequence_reserved))==10000
        assert c.scalar(select(m.devices.c.command_sequence))==1
        assert c.scalar(select(m.devices.c.pending_transition))==tid
        assert c.scalar(select(m.transitions.c.phase))=='ACTIVATION_SENT'
        assert c.scalar(text("SELECT last_sequence FROM mqtt_replay_state WHERE device_id='migration-control'"))==123
        assert c.execute(select(m.evidence)).first() is None # no invented historical packet receipt

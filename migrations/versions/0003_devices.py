"""Non-secret device identity bindings, leaving legacy compound keys intact."""
from alembic import op
import sqlalchemy as sa
revision='0003_devices'
down_revision='0002_outbox'
branch_labels=depends_on=None

def upgrade():
    op.create_table('telemetry_devices',
        sa.Column('device_id',sa.String(48),primary_key=True),
        sa.Column('database_device_id',sa.Integer(),nullable=False,unique=True),
        sa.Column('topic',sa.String(64),nullable=False,unique=True),
        sa.Column('key_epoch',sa.Integer(),nullable=False),
        sa.Column('crypto_profile',sa.String(32),nullable=False),
        sa.Column('enabled',sa.Boolean(),nullable=False,server_default='true'),
        sa.CheckConstraint('database_device_id > 0 AND key_epoch > 0',name='ck_devices_numbers'),
        sa.CheckConstraint("topic = 'iot/sensors/' || device_id",name='ck_devices_topic'),
        sa.CheckConstraint("crypto_profile = 'Ascon-AEAD128'",name='ck_devices_profile'))

def downgrade():
    raise RuntimeError('Device bindings require reviewed migration; no automatic deletion')

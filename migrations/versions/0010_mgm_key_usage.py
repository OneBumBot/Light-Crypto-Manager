"""Per-key conservative MGM usage authority; deliberately no historical backfill."""
from alembic import op
revision='0010_mgm_key_usage'
down_revision='0009_component_heartbeat'
branch_labels=depends_on=None

def upgrade():
    import sqlalchemy as sa
    op.create_table('crypto_key_usage',
        sa.Column('device_id',sa.String(48),primary_key=True),
        sa.Column('key_epoch',sa.Integer(),primary_key=True),
        sa.Column('profile_id',sa.String(64),primary_key=True),
        sa.Column('key_reference',sa.String(96),nullable=False),
        sa.Column('nonce_policy',sa.String(48),nullable=False),
        *[sa.Column(name,sa.BigInteger(),nullable=False) for name in [
            'reserved_invocations','reserved_blocks','max_invocations','max_blocks','verify_attempts','max_verify_attempts']],
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),
        sa.CheckConstraint('reserved_invocations>=0 AND reserved_invocations<=max_invocations AND max_invocations<=1048576 AND reserved_blocks=320*reserved_invocations AND reserved_blocks<=max_blocks AND max_blocks<=335544320 AND verify_attempts>=0 AND verify_attempts<=max_verify_attempts AND max_verify_attempts<=1048576',name='ck_mgm_budget'))
    op.create_table('crypto_usage_reservations',
        sa.Column('request_id',sa.String(36),primary_key=True),
        sa.Column('device_id',sa.String(48),nullable=False),
        sa.Column('key_epoch',sa.Integer(),nullable=False),
        sa.Column('profile_id',sa.String(64),nullable=False),
        *[sa.Column(name,sa.BigInteger(),nullable=False) for name in ['first_sequence','last_sequence','invocations','blocks']],
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.CheckConstraint('first_sequence>0 AND last_sequence>=first_sequence AND invocations=last_sequence-first_sequence+1 AND blocks=320*invocations',name='ck_mgm_reservation'))

def downgrade():
    raise RuntimeError('Reviewed key rotation and usage history preservation required')

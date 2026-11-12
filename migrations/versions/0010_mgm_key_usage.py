"""Per-key conservative MGM usage authority; deliberately no historical backfill."""
from alembic import op
revision='0010_mgm_key_usage'
down_revision='0009_component_heartbeat'
branch_labels=depends_on=None

def upgrade():
    from src.kuz_usage import usage,reservations
    usage.create(op.get_bind())
    reservations.create(op.get_bind())

def downgrade():
    raise RuntimeError('Reviewed key rotation and usage history preservation required')

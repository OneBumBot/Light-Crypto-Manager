"""Add diagnostic heartbeat, without changing crypto/telemetry authority."""
from alembic import op
import sqlalchemy as sa
revision = '0009_component_heartbeat'
down_revision = '0008_control_evidence'
branch_labels = depends_on = None


def upgrade():
    op.create_table('component_heartbeats',
        sa.Column('component', sa.String(32), primary_key=True),
        sa.Column('instance', sa.String(64), primary_key=True),
        sa.Column('checked_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ready', sa.Boolean(), nullable=False))


def downgrade():
    raise RuntimeError('Reviewed diagnostic history migration required')

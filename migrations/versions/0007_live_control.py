"""Add live control tables without touching telemetry replay or old policies."""
import json
from pathlib import Path
from alembic import op
from sqlalchemy import text
revision='0007_live_control'
down_revision='0006_policy_control'
branch_labels=depends_on=None

def upgrade():
    for sql in json.loads((Path(__file__).parents[1]/'live_control_snapshot.json').read_text()):
        op.get_bind().execute(text(sql))

def downgrade():
    raise RuntimeError('Live command/nonce authority cannot be discarded; reviewed migration required')

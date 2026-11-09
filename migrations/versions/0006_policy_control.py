"""Independent persisted command epoch/sequence; no live control activation."""
import json
from pathlib import Path
from alembic import op
from sqlalchemy import text
revision='0006_policy_control'
down_revision='0005_policy'
branch_labels=depends_on=None

def upgrade():
    for statement in json.loads((Path(__file__).parents[1]/'policy_control_counter_snapshot.json').read_text()):
        op.get_bind().execute(text(statement))

def downgrade():
    raise RuntimeError('Command counters must not be reset; reviewed migration required')

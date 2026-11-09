"""Policy journal and dry-run decisions. Preserves all prior tables and data."""
import json
from pathlib import Path
from alembic import op
from sqlalchemy import text
revision='0005_policy'
down_revision='0004_ml'
branch_labels=depends_on=None


def upgrade():
    for statement in json.loads((Path(__file__).parents[1]/'policy_snapshot.json').read_text()):
        op.get_bind().execute(text(statement))


def downgrade():
    raise RuntimeError('Policy audit may be in use; reviewed non-destructive migration required')

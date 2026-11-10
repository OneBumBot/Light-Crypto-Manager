"""Preserve authenticated effective receipts independently of outbox retention."""
import json
from pathlib import Path
from alembic import op
from sqlalchemy import text
revision='0008_control_evidence'
down_revision='0007_live_control'
branch_labels=depends_on=None

def upgrade():
    for sql in json.loads((Path(__file__).parents[1]/'control_evidence_snapshot.json').read_text()):
        op.get_bind().execute(text(sql))
    # Existing stage8 draft rows are NOT backfilled with invented packet digests.
    # They retain their outbox references; next new transition creates a full receipt.


def downgrade():
    raise RuntimeError('Effective receipts are security audit; reviewed migration required')

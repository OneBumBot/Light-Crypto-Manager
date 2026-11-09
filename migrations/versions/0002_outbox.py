"""Transactional telemetry outbox and ingestion counters; no legacy PK changes."""
import json
from pathlib import Path
from alembic import op
from sqlalchemy import text
revision = '0002_outbox'
down_revision = '0001_legacy'
branch_labels = depends_on = None

def upgrade():
    for sql in json.loads((Path(__file__).parents[1] / 'outbox_snapshot.json').read_text()):
        op.get_bind().execute(text(sql))

def downgrade():
    raise RuntimeError('Outbox may contain undelivered data; manual review required')

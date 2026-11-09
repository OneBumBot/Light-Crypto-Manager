"""Bounded ML delivery feed, immutable model identities and idempotent evaluations."""
import json
from pathlib import Path
from alembic import op
from sqlalchemy import text
revision='0004_ml'
down_revision='0003_devices'
branch_labels=depends_on=None

def upgrade():
    c=op.get_bind()
    for sql in json.loads((Path(__file__).parents[1]/'ml_snapshot.json').read_text()):c.execute(text(sql))
    c.execute(text('''INSERT INTO ml_observations(id,device_id,key_epoch,sequence_number,mongo_confirmed_at)
        SELECT id,device_id,key_epoch,sequence_number,delivered_at FROM telemetry_outbox
        WHERE status='delivered' ORDER BY delivered_at,id LIMIT 100000'''))
    c.execute(text('''INSERT INTO ml_feed_state(id,retained,published,overflow_skipped)
        SELECT 1,(SELECT count(*) FROM ml_observations),(SELECT count(*) FROM ml_observations),
        GREATEST(0,(SELECT count(*) FROM telemetry_outbox WHERE status='delivered')-100000)'''))

def downgrade():
    raise RuntimeError('ML history may be in use; reviewed non-destructive migration required')

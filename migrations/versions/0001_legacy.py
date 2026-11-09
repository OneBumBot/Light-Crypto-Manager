"""Frozen stage-4 baseline: validate existing tables before creating missing ones."""
import json
from pathlib import Path
from alembic import op
from sqlalchemy import inspect, text

revision = '0001_legacy'
down_revision = None
branch_labels = depends_on = None


def upgrade():
    connection = op.get_bind()
    snapshot = json.loads((Path(__file__).parents[1] / 'legacy_snapshot.json').read_text())
    inspector = inspect(connection)
    present = set(inspector.get_table_names())
    # Validate all existing tables before any DDL. No blind stamp or alteration.
    for name, spec in snapshot.items():
        if name not in present:
            continue
        columns = {c['name']: {'type': c['type'].compile(dialect=connection.dialect),
                              'nullable': c['nullable']} for c in inspector.get_columns(name)}
        pk = inspector.get_pk_constraint(name)['constrained_columns']
        unique = [c['column_names'] for c in inspector.get_unique_constraints(name)]
        if columns != spec['columns'] or pk != spec['pk'] or sorted(unique) != sorted(spec['unique']):
            raise RuntimeError('Legacy schema mismatch; manual review required: ' + name)
    for name, spec in snapshot.items():
        if name not in present:
            connection.execute(text(spec['sql']))


def downgrade():
    raise RuntimeError('Baseline downgrade is intentionally non-destructive; manual review required')

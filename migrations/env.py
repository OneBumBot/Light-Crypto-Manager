from alembic import context
from sqlalchemy import create_engine, pool
from src.runtime import database_url
from src.web.models import db
from src.replay import metadata as replay_metadata

from src.outbox import metadata as outbox_metadata
from src.devices import metadata as device_metadata
from src.ml_storage import metadata as ml_metadata
from src.security_events import metadata as security_metadata
from src.policy.models import metadata as policy_metadata
from src.device_control.models import metadata as control_metadata
metadata = [control_metadata,security_metadata, policy_metadata,db.metadata, replay_metadata, outbox_metadata, device_metadata, ml_metadata]

connection = context.config.attributes.get('connection')

def run(connection):
    context.configure(connection=connection, target_metadata=metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()

if connection is not None:
    run(connection)
else:
    engine = create_engine(database_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        run(connection)
    engine.dispose()

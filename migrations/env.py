from alembic import context
from sqlalchemy import create_engine, pool
from src.runtime import database_url
from src.web.models import db
from src.replay import metadata as replay_metadata

from src.outbox import metadata as outbox_metadata
from src.devices import metadata as device_metadata
metadata = [db.metadata, replay_metadata, outbox_metadata, device_metadata]

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

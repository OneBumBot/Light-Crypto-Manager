"""Serialized, transactional Alembic upgrade (new and legacy PostgreSQL)."""
from pathlib import Path
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from src.runtime import database_url


def upgrade(engine):
    config = Config(str(Path(__file__).resolve().parents[1] / 'alembic.ini'))
    with engine.begin() as connection:
        connection.execute(text('SELECT pg_advisory_xact_lock(734819205)'))
        config.attributes['connection'] = connection
        command.upgrade(config, 'head')


def main():
    engine = create_engine(database_url(), pool_pre_ping=True)
    try:
        upgrade(engine)
        print('PostgreSQL migrations applied')
    finally:
        engine.dispose()

if __name__ == '__main__':
    main()

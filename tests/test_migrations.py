from sqlalchemy import inspect, text
import pytest
from src.migrate import upgrade

pytestmark = pytest.mark.postgres


def test_migrate_existing_preserves_data(legacy_postgres_db):
    engine = legacy_postgres_db.db.engine
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO mqtt_replay_state VALUES ('receiver','migration',1,12)"))
        conn.execute(text('INSERT INTO "Sensor_Data" ("Record_ID","Temperature") VALUES (818,12.5)'))
    upgrade(engine)
    upgrade(engine)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT last_sequence FROM mqtt_replay_state WHERE device_id='migration'")).scalar_one() == 12
        assert float(conn.execute(text('SELECT "Temperature" FROM "Sensor_Data" WHERE "Record_ID"=818')).scalar_one()) == 12.5
        assert conn.execute(text('SELECT version_num FROM alembic_version')).scalar_one()


def test_migrate_empty_schema(legacy_postgres_db):
    engine = legacy_postgres_db.db.engine
    # Dedicated nested schema, never drops application tables/volumes.
    with engine.begin() as conn:
        conn.execute(text('CREATE SCHEMA fresh_migration'))
        conn.execute(text('SET LOCAL search_path TO fresh_migration'))
        from alembic.config import Config
        from alembic import command
        config = Config('alembic.ini')
        config.attributes['connection'] = conn
        command.upgrade(config, 'head')
        assert 'Sensor_Data' in inspect(conn).get_table_names()
        assert 'mqtt_replay_state' in inspect(conn).get_table_names()
        conn.execute(text('DROP SCHEMA fresh_migration CASCADE'))


def test_migration_rejects_incompatible_schema(legacy_postgres_db):
    engine = legacy_postgres_db.db.engine
    with engine.begin() as conn:
        conn.execute(text('ALTER TABLE "Sensor_Data" ADD COLUMN unexpected integer'))
    with pytest.raises(RuntimeError, match='schema mismatch'):
        upgrade(engine)
    with engine.connect() as conn:
        assert 'unexpected' in {c['name'] for c in inspect(conn).get_columns('Sensor_Data')}

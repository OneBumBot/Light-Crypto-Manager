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


def test_stage5_upgrade_preserves_outbox_and_backfills_ml(legacy_postgres_db):
    from alembic.config import Config
    from alembic import command
    import uuid
    from datetime import datetime,timezone
    engine=legacy_postgres_db.db.engine
    event_id=str(uuid.uuid4());now=datetime.now(timezone.utc)
    with engine.begin() as c:
        config=Config('alembic.ini');config.attributes['connection']=c
        command.upgrade(config,'0003_devices')
        c.execute(text("INSERT INTO mqtt_replay_state VALUES ('receiver','legacy-ml',1,99)"))
        c.execute(text('''INSERT INTO telemetry_outbox(id,device_id,key_epoch,sequence_number,payload,created_at,
            status,attempts,available_at,delivered_at) VALUES (:id,'legacy-ml',1,99,'{}',:now,'delivered',1,:now,:now)'''),{'id':event_id,'now':now})
    upgrade(engine);upgrade(engine)
    with engine.connect() as c:
        assert c.scalar(text("SELECT last_sequence FROM mqtt_replay_state WHERE device_id='legacy-ml'"))==99
        assert c.scalar(text('SELECT id FROM telemetry_outbox'))==event_id
        assert c.scalar(text('SELECT id FROM ml_observations'))==event_id
        assert c.scalar(text('SELECT retained FROM ml_feed_state'))==1

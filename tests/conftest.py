"""Only PostgreSQL tests connect to a DB; each uses its own disposable schema."""

import os
import uuid
import json
import tempfile
import atexit
import shutil
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from src.runtime import database_url

TEST_URL = os.environ.get('TEST_DATABASE_URL')
SCHEMA = 'lcm_test_' + uuid.uuid4().hex
if TEST_URL:
    normalized = database_url(TEST_URL)
    test_url = make_url(normalized).update_query_dict({'options': f'-csearch_path={SCHEMA}'})
    os.environ['DATABASE_URL'] = test_url.render_as_string(hide_password=False)
else:
    os.environ['DATABASE_URL'] = 'postgresql+psycopg://localhost/lightcrypto_test'
# Public fixtures; no real key is ever required by the unit tests.
os.environ['FLASK_SECRET_KEY'] = 'public-unit-test-session-key'
os.environ['ASCON_KEY_HEX'] = bytes(range(16)).hex()


@pytest.fixture
def legacy_postgres_db():
    if not TEST_URL:
        pytest.skip('set TEST_DATABASE_URL for PostgreSQL integration tests')
    from src.web import app as web

    admin = create_engine(database_url(TEST_URL))
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{SCHEMA}"'))
    try:
        with web.app.app_context():
            web.db.create_all()
            from src.replay import metadata
            metadata.create_all(web.db.engine)
            yield web
            web.db.session.remove()
    finally:
        with web.app.app_context():
            web.db.session.remove()
            web.db.engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{SCHEMA}" CASCADE'))
        admin.dispose()

# Public test keys; isolated from the real Compose key registry.
TEST_REGISTRY = {
    name: {'topic': 'iot/sensors/'+name, 'key_epoch': 1, 'database_device_id': i,
           'key_hex': bytes(range(offset, offset+16)).hex()}
    for name,i,offset in [('raspb1',1,0),('smoke',2,16)]
}
_registry_dir = Path(tempfile.mkdtemp(prefix='lcm-registry-test-'))
_registry_file = _registry_dir/'registry.json'
_registry_file.write_text(json.dumps(TEST_REGISTRY))
_registry_file.chmod(0o600)
os.environ['DEVICE_REGISTRY_FILE'] = str(_registry_file)
atexit.register(shutil.rmtree, _registry_dir)

@pytest.fixture
def registry():
    return json.loads(json.dumps(TEST_REGISTRY))

@pytest.fixture
def postgres_db(legacy_postgres_db):
    from src.migrate import upgrade
    upgrade(legacy_postgres_db.db.engine)
    yield legacy_postgres_db

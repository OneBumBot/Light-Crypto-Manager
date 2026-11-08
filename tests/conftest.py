"""Only PostgreSQL tests connect to a DB; each uses its own disposable schema."""

import os
import uuid

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
def postgres_db():
    if not TEST_URL:
        pytest.skip('set TEST_DATABASE_URL for PostgreSQL integration tests')
    from src.web import app as web

    admin = create_engine(database_url(TEST_URL))
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{SCHEMA}"'))
    try:
        with web.app.app_context():
            web.db.create_all()
            yield web
            web.db.session.remove()
    finally:
        with web.app.app_context():
            web.db.session.remove()
            web.db.engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{SCHEMA}" CASCADE'))
        admin.dispose()

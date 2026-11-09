import base64
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import inspect, select, text

from src.brocker.mqtt_brocker import on_message, process_packet
from src.runtime import ascon_key
from web_helpers import csrf_token, headers
from src.telemetry import encode_packet, load_registry
from src.web.models import (
    Algorithm, Anomaly, DeviceConfiguration, LogJournal, SensorData, TagJournal, User,
)

pytestmark = pytest.mark.postgres


def packet(device='raspb1', temperature=65, timestamp=None, sequence=1):
    timestamp = timestamp or datetime.now(timezone.utc)
    sensor = {'temperature': temperature, 'humidity': 50, 'timestamp': timestamp.isoformat()}
    return encode_packet(sensor, load_registry(), device, sequence)


def seed_device(web):
    date = datetime(2026, 1, 1)
    web.db.session.add(TagJournal(Tag_ID=1, Tag_Name='raspb1-main', Creation_Date=date))
    web.db.session.add(DeviceConfiguration(Device_ID=1, Tag_ID=1, Algorithm_ID=1,
                                           Configuration_Update_Date=date))
    from src.devices import provision
    provision(web.db.session.connection(),load_registry())
    web.db.session.commit()


def test_schema_and_web_read_write(postgres_db):
    web = postgres_db
    assert len(inspect(web.db.engine).get_table_names()) == 23
    assert web.create_default_users() == 0  # No password means no default account.
    user = User(username='smoke-admin', email='admin@example.test', role='admin')
    user.set_password('public-test-password')
    web.db.session.add(user)
    web.db.session.add(Algorithm(Algorithm_ID=1, Algorithm_Name='Ascon-AEAD128'))
    log = LogJournal(Log_Type_ID=1, Record_Date=datetime(2026, 1, 1))
    web.db.session.add(log)
    web.db.session.flush()
    web.db.session.add(SensorData(Record_ID=log.Record_ID, Temperature=25, Humidity=50))
    web.db.session.commit()
    web.app.config.update(TESTING=True)
    with web.app.test_client() as client:
        response = client.post('/login', data={
            'username': 'smoke-admin', 'password': 'public-test-password',
            'csrf_token': csrf_token(client),
        })
        assert response.status_code == 302
        assert client.get('/').status_code == 200
        for values in web.latest_data.values():
            values.clear()
        assert client.get('/api/latest-data').json['temperature'] == [25.0]
        assert client.put('/api/algorithms/1', json={'Algorithm_Name': 'updated'}, headers=headers(client)).status_code == 200
        assert web.db.session.get(Algorithm, 1).Algorithm_Name == 'updated'
        assert client.delete('/api/algorithms/1', headers=headers(client)).status_code == 200
        assert web.db.session.get(Algorithm, 1) is None


def test_init_db_cli_is_idempotent(postgres_db):
    result = subprocess.run([sys.executable, '-m', 'src.web.app', 'init-db'],
                            env=dict(os.environ), capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, 'init-db CLI failed'
    assert len(inspect(postgres_db.db.engine).get_table_names()) == 23


def test_bootstrap_is_explicit_and_preserves_passwords(postgres_db, monkeypatch):
    web = postgres_db
    for role in ['ADMIN', 'OPERATOR', 'VIEWER']:
        monkeypatch.delenv(f'BOOTSTRAP_{role}_PASSWORD', raising=False)
    assert web.create_default_users() == 0
    monkeypatch.setenv('BOOTSTRAP_ADMIN_PASSWORD', 'public-first-password')
    assert web.create_default_users() == 1
    monkeypatch.setenv('BOOTSTRAP_ADMIN_PASSWORD', 'public-replacement-password')
    assert web.create_default_users() == 0
    assert web.db.session.scalar(select(User)).check_password('public-first-password')


@pytest.mark.parametrize('temperature,age,cause', [(65, 0, 0), (25, 1, 1), (25, 0, None)])
def test_receiver_anomaly_rules(postgres_db, temperature, age, cause):
    web = postgres_db
    seed_device(web)
    now = datetime.now(timezone.utc)
    data = process_packet(packet(temperature=temperature, timestamp=now-timedelta(seconds=age)),
                          load_registry(), web.db.engine, "iot/sensors/raspb1", now=now)
    assert data['temperature'] == temperature
    rows = web.db.session.scalars(select(Anomaly)).all()
    assert [row.Anomaly_Cause_ID for row in rows] == ([] if cause is None else [cause])


def test_receiver_untrusted_device_and_tamper(postgres_db):
    web = postgres_db
    seed_device(web)
    from src.telemetry import InvalidTelemetry
    with pytest.raises(InvalidTelemetry):
        packet(device="raspb1' OR 1=1 --")
    assert web.db.session.scalar(select(Anomaly)) is None
    value = packet()
    ct = base64.b64decode(value['ciphertext'])
    value['ciphertext'] = base64.b64encode(ct[:-1] + bytes([ct[-1] ^ 1])).decode()
    with pytest.raises(ValueError, match='authenticated'):
        process_packet(value, load_registry(), web.db.engine, "iot/sensors/raspb1")
    assert web.db.session.scalar(select(Anomaly)) is None


def test_receiver_rolls_back_and_recovers(postgres_db):
    web = postgres_db
    seed_device(web)
    # A temporary constraint makes INSERT fail after the successful SELECT.
    with web.db.engine.begin() as connection:
        connection.execute(text('ALTER TABLE "Anomalies" ADD CONSTRAINT reject_cause CHECK ("Anomaly_Cause_ID" < 0)'))
    class Message:
        payload = json.dumps(packet()).encode()
        topic = 'iot/sensors/raspb1'
    on_message(None, {'registry': load_registry(), 'engine': web.db.engine}, Message())
    with web.db.engine.begin() as connection:
        assert connection.execute(text('SELECT count(*) FROM "Anomalies"')).scalar_one() == 0
        connection.execute(text('ALTER TABLE "Anomalies" DROP CONSTRAINT reject_cause'))
    process_packet(packet(), load_registry(), web.db.engine, "iot/sensors/raspb1")
    assert web.db.session.scalar(select(Anomaly)) is not None

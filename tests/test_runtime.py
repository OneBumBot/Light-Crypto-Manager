import json
import os
import subprocess
import sys

import pytest

from src.runtime import ascon_key, database_url


def test_imports_do_not_connect_or_create_logs():
    env = dict(os.environ)
    for name in ['DATABASE_URL', 'ASCON_KEY_HEX', 'FLASK_SECRET_KEY']:
        env.pop(name, None)
    result = subprocess.run([sys.executable, '-c', '''
from unittest.mock import patch
with patch('socket.socket.connect', side_effect=AssertionError('network on import')), \\
     patch('logging.FileHandler', side_effect=AssertionError('file on import')):
    import src.publisher.mqtt_pub
    import src.brocker.mqtt_brocker
    import src.web.app
'''], env=env, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('value', ['', 'invalid', '00', 'gg' * 16, '00' * 17])
def test_invalid_key_is_rejected_without_echo(monkeypatch, value):
    monkeypatch.setenv('ASCON_KEY_HEX', value)
    with pytest.raises(ValueError, match='32 hexadecimal characters'):
        ascon_key()


def test_database_requires_postgres(monkeypatch):
    monkeypatch.delenv('DATABASE_URL', raising=False)
    with pytest.raises(ValueError, match='postgresql'):
        database_url()
    with pytest.raises(ValueError, match='postgresql'):
        database_url('mssql+pymssql://localhost/old')
    assert database_url('postgresql://localhost/test') == 'postgresql+psycopg://localhost/test'


def test_publisher_packet_is_readable_by_web(registry):
    from src.publisher.mqtt_pub import decrypt_data, encrypt_data
    from src.web.app import decrypt_ascon_data

    sensor = {'temperature': 25.0, 'humidity': 50.0, 'timestamp': '2026-11-08T00:00:00+00:00'}
    packet = encrypt_data(json.dumps(sensor), registry, sequence_number=1)
    assert json.loads(decrypt_data(packet, registry, "iot/sensors/raspb1")) == sensor
    assert decrypt_ascon_data(packet, "iot/sensors/raspb1", registry) == sensor


def test_mqtt_clients_use_callback_v2(monkeypatch, tmp_path):
    password = tmp_path / "password"
    password.write_text("public-test-password")
    monkeypatch.setenv("MQTT_USERNAME", "web")
    monkeypatch.setenv("MQTT_PASSWORD_FILE", str(password))
    monkeypatch.setenv("MQTT_INSECURE_TEST_MODE", "1")
    monkeypatch.setenv("APP_ENV", "test")
    import paho.mqtt.client as mqtt
    from src.web.app import create_mqtt_client

    client = create_mqtt_client()
    assert client.callback_api_version == mqtt.CallbackAPIVersion.VERSION2
    client.disconnect()


def test_login_page_and_auth_redirect():
    from src.web.app import app

    with app.test_client() as client:
        assert client.get('/login').status_code == 200
        response = client.get('/')
        assert response.status_code == 302
        assert '/login' in response.headers['Location']

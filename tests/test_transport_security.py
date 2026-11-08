import paho.mqtt.client as mqtt
import pytest
from src.mqtt_transport import configure_client


@pytest.fixture
def transport(monkeypatch,tmp_path):
    path=tmp_path/'password'
    path.write_text('public-test-password')
    monkeypatch.setenv('MQTT_USERNAME','publisher')
    monkeypatch.setenv('MQTT_PASSWORD_FILE',str(path))
    for field in ['MQTT_CA_FILE','MQTT_INSECURE_TEST_MODE','APP_ENV']:
        monkeypatch.delenv(field,raising=False)
    return mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)


def test_no_silent_plaintext_fallback(transport):
    with pytest.raises(ValueError,match='MQTT_CA_FILE'):
        configure_client(transport)


def test_plaintext_flag_restricted_to_test_environment(transport,monkeypatch):
    monkeypatch.setenv('MQTT_INSECURE_TEST_MODE','1')
    monkeypatch.setenv('APP_ENV','production')
    with pytest.raises(ValueError,match='restricted'):
        configure_client(transport)
    monkeypatch.setenv('APP_ENV','test')
    assert configure_client(transport) is transport


def test_credentials_required_even_in_test_mode(transport,monkeypatch):
    monkeypatch.setenv('MQTT_INSECURE_TEST_MODE','1')
    monkeypatch.setenv('APP_ENV','test')
    monkeypatch.delenv('MQTT_USERNAME')
    with pytest.raises(ValueError,match='MQTT_USERNAME'):
        configure_client(transport)

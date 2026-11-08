"""Shared authenticated MQTT transport. TLS is mandatory unless explicitly testing."""
import os
from pathlib import Path
import ssl


def configure_client(client, *, username=None, password_file=None, ca_file=None):
    username = username or os.environ.get('MQTT_USERNAME')
    password_file = password_file or os.environ.get('MQTT_PASSWORD_FILE')
    if not username or not password_file:
        raise ValueError('MQTT_USERNAME and MQTT_PASSWORD_FILE are required')
    password = Path(password_file).read_text().strip()
    if not password:
        raise ValueError('Empty MQTT password file')
    client.username_pw_set(username, password)
    if os.environ.get('MQTT_INSECURE_TEST_MODE') == '1':
        if os.environ.get('APP_ENV') != 'test':
            raise ValueError('Insecure MQTT is restricted to APP_ENV=test')
        return client
    ca_file = ca_file or os.environ.get('MQTT_CA_FILE')
    if not ca_file:
        raise ValueError('MQTT_CA_FILE is required')
    context = ssl.create_default_context(cafile=ca_file)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    client.tls_set_context(context)
    return client

import os

from src.runtime import database_url


class Config:
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY")
    # The credential-free default only permits imports without a configured server.
    # Runtime entrypoints require DATABASE_URL explicitly before any connection.
    SQLALCHEMY_DATABASE_URI = database_url(
        os.environ.get("DATABASE_URL", "postgresql+psycopg://localhost/lightcrypto")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    MQTT_BROKER_URL = os.environ.get("MQTT_HOST", "localhost")
    MQTT_BROKER_PORT = int(os.environ.get("MQTT_PORT", "8883"))
    MQTT_USERNAME = os.environ.get("MQTT_USERNAME", "")
    MQTT_KEEPALIVE = 60
    MQTT_TOPIC = os.environ.get("MQTT_TOPIC", "iot/sensors/#")

import os

class Config:
    # Flask
    SECRET_KEY = os.environ["FLASK_SECRET_KEY"]
    
    # MQTT Configuration
    MQTT_BROKER_URL = os.environ.get("MQTT_HOST", "localhost")
    MQTT_BROKER_PORT = 1883
    MQTT_USERNAME = ''
    MQTT_PASSWORD = os.environ.get("MQTT_PASSWORD", "")
    MQTT_KEEPALIVE = 60
    MQTT_TLS_ENABLED = False
    MQTT_TOPIC = 'iot/sensors/#'


    # MS SQL Server Configuration
    SQLALCHEMY_DATABASE_URI = os.environ["DATABASE_URL"]
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Ascon Encryption
    ASCON_KEY = bytes.fromhex(os.environ["ASCON_KEY_HEX"])

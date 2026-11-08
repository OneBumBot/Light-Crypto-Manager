#!/usr/bin/env python
from src.mqtt_transport import configure_client
import paho.mqtt.client as mqtt
import time
import numpy as np
import json
import os
from datetime import datetime, timezone
from src.telemetry import PROFILE, encode_packet, decode_packet, load_registry, strict_json
from src.sequence import next_sequence
import math

BROKER_HOST = os.environ.get("MQTT_HOST", "localhost")
BROKER_PORT = int(os.environ.get("MQTT_PORT", "8883"))
DEVICE_ID = os.environ.get("DEVICE_ID", "raspb1")
TOPIC = os.environ.get("MQTT_PUBLISH_TOPIC", "iot/sensors/" + DEVICE_ID)
CLIENT_ID = os.environ.get('MQTT_CLIENT_ID', DEVICE_ID)
ASCON_VARIANT = PROFILE


def encrypt_data(plaintext_json, registry, *, sequence_number, device_id=DEVICE_ID):
    return encode_packet(strict_json(plaintext_json), registry, device_id, sequence_number)


def decrypt_data(packet, registry, topic):
    return json.dumps(decode_packet(packet, topic, registry).sensor)


# Callback функции MQTT


def on_connect(client, userdata, flags, rc, properties):
    if rc == 0:
        print(f"[+] [{datetime.now()}] Подключено к MQTT брокеру")
    else:
        print(f"[-] [{datetime.now()}] Ошибка подключения. Код: {rc}")


def on_publish(client, userdata, mid, reason_code, properties):
    print(f"[*] [{datetime.now()}] Зашифрованное сообщение отправлено (ID: {mid})")


def on_disconnect(client, userdata, flags, rc, properties):
    if rc != 0:
        print(f"[!] [{datetime.now()}] Переподключение")


def main():
    # Создание MQTT клиента
    registry = load_registry()
    entry = registry[DEVICE_ID]
    if TOPIC != entry["topic"]:
        raise ValueError("Publisher topic does not match provisioned device")
    state_file = os.environ["PUBLISHER_STATE_FILE"]
    interval = float(os.environ.get("PUBLISH_INTERVAL", "10"))
    if not math.isfinite(interval) or interval <= 0:
        raise ValueError("PUBLISH_INTERVAL must be positive")
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=CLIENT_ID)
    configure_client(client)
    client.on_connect = on_connect
    client.on_publish = on_publish
    client.on_disconnect = on_disconnect

    # Основной цикл
    try:
        client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)

        client.loop_start()

        print(f"\n{'='*60}")
        print(f"IoT Device с Ascon-AEAD128 шифрованием")
        print(f"Device ID: {CLIENT_ID}")
        print(f"Алгоритм: {ASCON_VARIANT} (NIST SP 800-232)")
        print(f"{'='*60}\n")

        while True:
            # Сбор данных с датчиков
            sensor_data = {
                "temperature": round(float(np.clip(np.random.normal(loc=50, scale=15), -80, 150)), 2),
                "humidity": round(float(np.clip(np.random.normal(loc=70, scale=10), 0, 100)), 2),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

            # Преобразование в JSON
            plaintext_json = json.dumps(sensor_data)


            # Шифрование с Ascon-AEAD128
            start_time = time.time()
            encrypted_packet = encrypt_data(
                plaintext_json, registry, sequence_number=next_sequence(state_file, DEVICE_ID, entry["key_epoch"]))
            encryption_time = (time.time() - start_time) * 1000  # в миллисекундах
            print(f"[*] [{datetime.now()}]Зашифровано за {encryption_time:.2f} мс")
            print(f"[*] Размер: {len(plaintext_json)} → {len(json.dumps(encrypted_packet))} байт")

            # Отправка по MQTT
            payload = json.dumps(encrypted_packet)
            result = client.publish(TOPIC, payload, qos=1)
            result.wait_for_publish(timeout=10)
            if not result.is_published():
                raise TimeoutError("MQTT publish acknowledgment timed out")

            # Локальная проверка расшифровки (опционально)
            try:
                decrypted = decrypt_data(encrypted_packet, registry, TOPIC)
                print(f"[+] [{datetime.now()}] Проверка расшифровки успешна\n")
            except ValueError as e:
                print(f"[-] [{datetime.now()}] {e}\n")

            time.sleep(interval)  # Отправка каждые 10 секунд

    except KeyboardInterrupt:
        print("Остановка publisher")
    finally:
        client.disconnect()
        client.loop_stop()


if __name__ == "__main__":
    main()

#!/usr/bin/env python
from src.mqtt_transport import configure_client
import paho.mqtt.client as mqtt
import time
import numpy as np
import json
import os
from datetime import datetime, timezone
from src.web.ascon.ascon import ascon_encrypt, ascon_decrypt
from src.runtime import ascon_key
import base64

# Настройки MQTT брокера
BROKER_HOST = os.environ.get("MQTT_HOST", "localhost")
BROKER_PORT = int(os.environ.get("MQTT_PORT", "8883"))
TOPIC = os.environ.get("MQTT_PUBLISH_TOPIC", "iot/sensors/raspb1")
CLIENT_ID = os.environ.get('MQTT_CLIENT_ID', 'raspb1')

#Конфигурация
DEVICE_ID = 1 
ALGORITHM_ID = 1

# Настройки криптографии Ascon-AEAD128
# Ключ должен быть 16 байт (128 бит) для Ascon-AEAD128
ASCON_VARIANT = "Ascon-AEAD128"  # Стандарт NIST SP 800-232


def generate_nonce():
    """Генерация уникального nonce (16 байт для Ascon-AEAD128)"""
    return os.urandom(16)


def encrypt_data(plaintext_json, key, variant="Ascon-AEAD128"):
    """
    Шифрование данных с использованием Ascon-AEAD128

    Args:
        plaintext_json: JSON строка с данными
        key: 16-байтовый ключ
        variant: Вариант Ascon (по умолчанию Ascon-AEAD128)

    Returns:
        dict с зашифрованными данными и метаданными
    """
    plaintext = plaintext_json.encode('utf-8')
    nonce = generate_nonce()

    # Associated Data - незашифрованные метаданные (опционально)
    associated_data = json.dumps({
        "device_id": CLIENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }).encode('utf-8')
    # Шифрование с использованием Ascon-AEAD128
    ciphertext = ascon_encrypt(key, nonce, associated_data, plaintext, variant)

    # Формирование пакета для передачи
    encrypted_packet = {
        "nonce": base64.b64encode(nonce).decode('utf-8'),
        "associated_data": base64.b64encode(associated_data).decode('utf-8'),
        "ciphertext": base64.b64encode(ciphertext).decode('utf-8'),
        "algorithm": variant
    }
    return encrypted_packet


def decrypt_data(encrypted_packet, key):
    """
    Расшифровка данных (для тестирования)
    """
    nonce = base64.b64decode(encrypted_packet["nonce"])
    associated_data = base64.b64decode(encrypted_packet["associated_data"])
    ciphertext = base64.b64decode(encrypted_packet["ciphertext"])
    variant = encrypted_packet["algorithm"]

    plaintext = ascon_decrypt(key, nonce, associated_data, ciphertext, variant)

    if plaintext is None:
        raise ValueError("Ошибка аутентификации: данные повреждены!")

    return plaintext.decode('utf-8')

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
    key = ascon_key()
    interval = float(os.environ.get("PUBLISH_INTERVAL", "10"))
    if interval <= 0:
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
                "temperature": round(np.random.normal(loc=50, scale = 15), 2),
                "humidity": round(np.random.normal(loc=70.0, scale = 10), 2),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

            # Преобразование в JSON
            plaintext_json = json.dumps(sensor_data)


            # Шифрование с Ascon-AEAD128
            start_time = time.time()
            encrypted_packet = encrypt_data(
                plaintext_json, key, ASCON_VARIANT)
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
                decrypted = decrypt_data(encrypted_packet, key)
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

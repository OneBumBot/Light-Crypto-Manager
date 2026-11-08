#!/usr/bin/env python
import paho.mqtt.client as mqtt
import time
import numpy as np
import random
import json
import os
from datetime import datetime
from pyascon.ascon import ascon_encrypt, ascon_decrypt 
import base64

# Настройки MQTT брокера
BROKER_HOST = os.environ.get("MQTT_HOST", "localhost")
BROKER_PORT = 1883
TOPIC = "iot/sensors/device1"
CLIENT_ID = 'raspb1'

#Конфигурация
DEVICE_ID = 1 
ALGORITHM_ID = 1

# Настройки криптографии Ascon-AEAD128
# Ключ должен быть 16 байт (128 бит) для Ascon-AEAD128
ASCON_KEY = bytes.fromhex(os.environ["ASCON_KEY_HEX"])
ASCON_VARIANT = "Ascon-AEAD128"  # Стандарт NIST SP 800-232


def generate_nonce():
    """Генерация уникального nonce (16 байт для Ascon-AEAD128)"""
    return os.urandom(16)


def encrypt_data(plaintext_json, key, variant="Ascon-128"):
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
        "timestamp": datetime.now().isoformat()
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


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[+] [{datetime.now()}] Подключено к MQTT брокеру")
    else:
        print(f"[-] [{datetime.now()}] Ошибка подключения. Код: {rc}")


def on_publish(client, userdata, mid):
    print(f"[*] [{datetime.now()}] Зашифрованное сообщение отправлено (ID: {mid})")


def on_disconnect(client, userdata, rc):
    if rc != 0:
        print(f"[!] [{datetime.now()}] Переподключение")


# Создание MQTT клиента
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, CLIENT_ID)
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
            "timestamp": datetime.now().isoformat()
        }

        # Преобразование в JSON
        plaintext_json = json.dumps(sensor_data)

        print(f"[{datetime.now()}] Исходные данные:")
        print(f"  {plaintext_json}")

        # Шифрование с Ascon-AEAD128
        start_time = time.time()
        encrypted_packet = encrypt_data(
            plaintext_json, ASCON_KEY, ASCON_VARIANT)
        encryption_time = (time.time() - start_time) * 1000  # в миллисекундах
        print(f"[*] [{datetime.now()}]Зашифровано за {encryption_time:.2f} мс")
        print(f"[*] Размер: {len(plaintext_json)} → {len(json.dumps(encrypted_packet))} байт")

        # Отправка по MQTT
        payload = json.dumps(encrypted_packet)
        result = client.publish(TOPIC, payload, qos=1)

        # Локальная проверка расшифровки (опционально)
        try:
            decrypted = decrypt_data(encrypted_packet, ASCON_KEY)
            print(f"[+] [{datetime.now()}] Проверка расшифровки успешна\n")
        except ValueError as e:
            print(f"[-] [{datetime.now()}] {e}\n")

        time.sleep(10)  # Отправка каждые 10 секунд

except KeyboardInterrupt:
    print(f"\n[{datetime.now()}] Остановка устройства...")
    client.loop_stop()
    client.disconnect()
except Exception as e:
    import traceback
    print(f"[{datetime.now()}] Критическая ошибка:")
    print(traceback.format_exc())
    client.loop_stop()
    client.disconnect()

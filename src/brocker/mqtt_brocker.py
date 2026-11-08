#!/usr/bin/env python3
import paho.mqtt.client as mqtt
import json
import os
import base64
from datetime import datetime, timedelta
from ascon.ascon import ascon_decrypt
import pymssql


BROKER_HOST = os.environ.get("MQTT_HOST", "localhost")
BROKER_PORT = 1883
TOPIC = "iot/sensors/#"
ASCON_KEY = bytes.fromhex(os.environ["ASCON_KEY_HEX"])

DB_SERVER = os.environ["DB_SERVER"]
DB_USER = os.environ["DB_USER"]
DB_PASSWORD = os.environ["DB_PASSWORD"]
DB_NAME = "IoTMonitor"



def on_connect(client, userdata, flags, rc):
    client.subscribe(TOPIC)
    print(f"[{datetime.now()}] Подписка на топик: {TOPIC}\n")

def connect_to_db():
    try:
        db_conn = pymssql.connect(server = DB_SERVER, user = DB_USER, password = DB_PASSWORD, database = DB_NAME)
        print("Подключение удалось")
        return db_conn
    except Exception as e:
        print(f"Ошибка подключения к БД: {e}")
        return None


def on_message(client, userdata, msg):
    try:
        encrypted_packet = json.loads(msg.payload.decode())
        
        # 1. ТОПИК - показывает, куда отправлено сообщение
        topic = msg.topic
        
        # 2. ASSOCIATED DATA - содержит device_id и timestamp
        associated_data_bytes = base64.b64decode(encrypted_packet["associated_data"])
        metadata = json.loads(associated_data_bytes.decode('utf-8'))
        
        device_id = metadata.get("device_id", "unknown")
        timestamp = metadata.get("timestamp", "unknown")
        dt = datetime.now()
        d = dt - datetime.fromisoformat(timestamp) + timedelta(hours = 3)
        # Расшифровка данных
        nonce = base64.b64decode(encrypted_packet["nonce"])
        ciphertext = base64.b64decode(encrypted_packet["ciphertext"])
        variant = encrypted_packet["algorithm"]
        
        plaintext = ascon_decrypt(ASCON_KEY, nonce, associated_data_bytes, 
                                 ciphertext, variant)
        
        if plaintext:
            sensor_data = json.loads(plaintext.decode('utf-8'))
            
            if (sensor_data.get('temperature') > 60) or (sensor_data.get('humidity') > 70):
                q = f" select device_id, Configuration_Update_Date from device_configuration where tag_id = (select top(1) tag_id from tag_journal where tag_name like '{device_id}%' order by creation_date desc) order by configuration_update_date desc"
                cursor = conn.cursor()
                cursor.execute(q)
                x = cursor.fetchone()
                if x:
                    date = datetime.now()
                    q = "insert into anomalies ([Anomaly_Date], [Anomaly_Cause_ID] ,[Device_ID] ,[Configuration_Update_Date]) values (%d, 0, %d, %d)"
                    cursor.execute(q, (date,x[0],x[1]))
                    conn.commit()
            elif (d.total_seconds() > 0.5):
                q = f" select device_id, Configuration_Update_Date from device_configuration where tag_id = (select top(1) tag_id from tag_journal where tag_name like '{device_id}%' order by creation_date desc) order by configuration_update_date desc"
                cursor = conn.cursor()
                cursor.execute(q)
                x = cursor.fetchone()
                if x:
                    date = datetime.now()
                    q = "insert into anomalies ([Anomaly_Date], [Anomaly_Cause_ID] ,[Device_ID] ,[Configuration_Update_Date]) values (%d, 1, %d, %d)"
                    cursor.execute(q, (date,x[0],x[1]))
                    conn.commit()

            print(f"{'='*60}")
            print(f"Device ID: {device_id}")
            print(f"Topic: {topic}")
            print(f"Timestamp: {timestamp}")
            print(f"Data:")
            print(f"  Temp: {sensor_data.get('temperature')}°C")
            print(f"  Humidity: {sensor_data.get('humidity')}%")
            print(f"{'='*60}\n")
        else:
            print(f"[-] [{datetime.now()}] Ошибка аутентификации от {device_id}!")
            
    except Exception as e:
        import traceback
        print(f"Ошибка обработки: {e}")
        print(traceback.format_exc())
        conn.rollback()


conn = connect_to_db()
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.connect(BROKER_HOST, BROKER_PORT, 60)
client.loop_forever()


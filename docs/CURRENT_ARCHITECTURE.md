# Текущая архитектура

Дата: 2026-11-08, обновлено после этапа 2. PostgreSQL создана и проверена
на изолированной новой БД; полный MQTT обмен ещё не проверен. Исходная схема
этапа 1 сохранена в коммите `76ca884`; команды запуска — в RUNTIME.md.

```mermaid
flowchart LR
    P["publisher/mqtt_pub.py: синтетические temperature/humidity"]
    E["vendored web/ascon/ascon.py"]
    B["внешний MQTT broker: конфигурация сервера отсутствует"]
    R["brocker/mqtt_brocker.py: subscriber + правила"]
    A["vendored web/ascon/ascon.py"]
    D[("PostgreSQL: 14 таблиц существующей ORM")]
    W["Flask app.py: отдельный MQTT subscriber + HTTP + Socket.IO"]
    M["latest_data: 50 точек в памяти процесса"]
    U["браузер: Jinja, Bootstrap, Chart.js, Socket.IO"]
    N["iot-test.ipynb: offline Edge-IIoT RF/IF"]
    F["joblib.dump: pkl-файлы отсутствуют"]
    P --> E
    P -->|"JSON, iot/sensors/device1, publish QoS 1"| B
    B -->|"iot/sensors/#"| R
    B -->|"iot/sensors/#"| W
    R --> A
    W --> A
    R -->|"SELECT конфигурации / INSERT аномалий"| D
    W -->|"чтение истории, users, table CRUD частично"| D
    W --> M
    M -->|"HTTP latest-data / sensor_update"| U
    U -->|"session login / table API"| W
    N --> F
```

`brocker` не принимает серверные MQTT-соединения, не реализует broker и не запускает
Mosquitto. Flask и receiver — независимые подписчики; Flask не получает от receiver
расшифрованные события или сигналы аномалий. ML с ними не связан.

## Реальный поток данных

1. Publisher генерирует два числа и timestamp, сериализует JSON в UTF-8.
2. AAD — отдельный JSON: строковый device_id и второй timestamp; nonce 16 случайных
   байт. Encrypt возвращает ciphertext с 16-байтовым тегом.
3. Публикуется JSON-оболочка из четырёх полей: nonce, associated_data, ciphertext
   в base64 и algorithm строкой. Внешний broker маршрутизирует сообщения.
4. Receiver проверяет тег, читает метаданные, вычисляет задержку по UTC,
   применяет прежние правила и записывает только аномалии в PostgreSQL через
   параметризованный SELECT и INSERT в одной транзакции.
5. Web самостоятельно дешифрует пакет, теряет device_id из AAD и обновляет общий
   буфер всех датчиков. Сохранение телеметрии отключено. Socket.IO рассылает
   температуру/влажность/время без разделения по устройствам и без connect auth.
6. Браузер сначала запрашивает историю через `/api/latest-data`, затем слушает
   sensor_update. При пустом буфере web пытается читать Log_Journal JOIN Sensor_Data.
   Источник наполнения этих таблиц рабочим кодом текущей цепочки не установлен.

Транспорт настроен на TCP/1883. Все три процесса поддерживают MQTT username/password из окружения,
но TLS ещё не настраивается. Paho VERSION2, QoS подписок 1; publisher ожидает
подтверждение публикации с timeout. Подтверждения доставки/персистентность брокера
и end-to-end семантика не проверены. Повторная доставка обрабатывается как новое
событие; authenticated timestamp не используется как anti-replay.

## Хранение и жизненный цикл

Flask-SQLAlchemy и receiver используют PostgreSQL через SQLAlchemy 2.0/Psycopg 3,
с общим DATABASE_URL. Имена/PK 14 моделей сохранены, смешанный регистр SQL корректно
цитируется. init-db создаёт таблицы явно через create_all; эта операция не заменяет
Alembic. Данных/DDL исходного MSSQL нет, их миграция не выполнялась. FK пока нет.
Users обслуживает web, 13 таблиц доступны через ролевую карту. Простой PUT/DELETE
проверен на PostgreSQL; составные PK и отсутствующий CREATE остаются проблемами.

Module entrypoints запускаются из корня. Publisher/receiver не соединяются при
импорте. Web импорт создаёт app/engine без сетевого подключения и файлового логгера;
serve отдельно проверяет конфигурацию, включает MQTT только по WEB_MQTT_ENABLED=1
и запускает локальный dev server (debug=False, loopback по умолчанию).
Создание схемы и начальных пользователей — отдельные явные команды. Пустые bootstrap
пароли не создают пользователей, существующие пароли не изменяются.

Конфигурация передаётся окружением, образец — .env.example. Воспроизведение:
Python 3.12.16, pyproject dependency groups, uv.lock и экспорты requirements.
LOG_FILE включает файловый лог при старте; по умолчанию stderr. Есть автоматические
проверки импорта, AEAD и PostgreSQL. Compose, миграций и CI ещё нет. Полный MQTT
контур и фактическое исполнение ARM64 остаются непроверенными.

Notebook работает отдельно в Kaggle-подобном окружении. Набор сетевых flow-признаков
не совпадает с decrypted JSON датчиков. Модели сохраняются без preprocessing/schema;
обратной связи от ML к криптографической части не реализовано.

FastAPI, отдельный worker как оформленный сервис, Policy Engine,
профили «Магмы»/CRISP, защищённые команды и anti-replay в этой архитектуре отсутствуют.
Их целевой план приведён отдельно в DEVELOPMENT_STATUS.md.

# Уточнение 8-fix: недоверенные типы и QoS 1

Outer `profile` проверяется как точный `str` до membership в `BY_ALGORITHM`.
Любой недопустимый JSON-тип, включая list/object, даёт `InvalidTelemetry`.
Проверенные Ascon-AEAD128 и AES-128-GCM сохраняют прежний формат, параметры и AAD
binding. Некорректный пакет не продвигает replay и не создаёт Outbox/effective
receipt. Reject observation намеренно не содержит неподтверждённую identity.
Receiver делает manual QoS1 ACK после durable reject audit либо успешного
admission/replay commit. При ошибке PG/commit ACK не выдаётся: disconnect и
persistent-session redelivery сохраняются. Broker PUBACK издателю подтверждает
только приём брокером, а не application admission/ACK receiver.

На исходном parser в изолированном TLS-стенде воспроизведены повторные подключения
после list/object profile; после исправления bounded negative tests проверяют
SQL/Mongo/evidence, последующую telemetry, connection logs и явный restart
receiver с той же persistent session. Детали: STAGE8_FIX_RESULTS.md и
MQTT_MALFORMED_INPUT_AUDIT.md. Это ограниченный эксперимент, не нагрузочный тест.

# Этап 8 — действующее расширение telemetry v2

Wire fields и AAD остаются прежними. Разрешены Ascon-AEAD128 (profile ID
ascon-aead128-v1,16-byte random nonce) и AES-128-GCM (aes-128-gcm-v1,12-byte nonce,
16-byte tag). AESGCM uses independent128-bit key, nonce epoch32BE||sequence64BE.
Алгоритм выбирается по explicit registry; AAD profile должен совпасть с outer
profile, key/device/topic/epoch binding проверяется до admission. Unknown/ошибка
AEAD не дают fallback. Sequence/replay общий между профилями одного device/epoch.
Для AES используется только прошедший live provisioning/lease Device Agent;
stateless encode_packet сам не выделяет безопасный sequence.

telemetry_devices.crypto_profile сохраняет legacy Ascon binding; это НЕ текущий
фактически подтверждённый profile. Для managed device server дополнительно
проверяет live_control_devices и bounded transition. Только receiver admission
transaction пишет effective receipt; web live consumer не подтверждает effective.
Control v2 — отдельные topics/domain/HMAC keys/replay counters; это не telemetry
schema3 и не изменение старых Ascon пакетов. Подробности SECURE_CONTROL_PROTOCOL.md,
CRYPTO_KEY_AND_NONCE_MANAGEMENT.md. Ниже историческая схема этапов4–5, её утверждение
«единственный профиль» заменено этим расширением.

# Дополнение этапа 5: протокол v2 сохранён

Формат ciphertext/AAD и диапазоны ниже не менялись. Дополнительно перед admission
проверяется PostgreSQL telemetry_devices: enabled/device/topic/epoch/profile и
numeric ID должны совпадать с приватным registry. Один PG commit receiver теперь
содержит replay-state, аномалию и outbox; затем отдельный relay пишет историю в
MongoDB. QoS1 manual ACK — после commit. Источник anti-replay — PostgreSQL, не
MongoDB. Web остаётся отдельным live consumer, постоянную историю сам не пишет.
Схемой управляет Alembic, 19 таблиц включая legacy и служебные. Старые упоминания
create_all/отсутствующего outbox ниже описывают только этап4 и заменены этим
уточнением. Гарантии и ограничения — OUTBOX.md, схема хранения — TELEMETRY_SCHEMA.md.

## Схема и исходные проверки этапа 4

# MQTT telemetry v2

Версия 1 этапа 3 больше не принимается. Неявного fallback/legacy режима нет.
Publisher, receiver, web и smoke используют общий модуль src/telemetry.py.

Внешний JSON имеет ровно schema_version (целое 2), profile (Ascon-AEAD128),
nonce, associated_data и ciphertext. Три последних поля — строгий Base64.
Максимальный payload — 8192 байта; broker также ограничивает message_size_limit
8192 и полный MQTT packet 12288. До JSON/дешифрования проверяется размер.
Nonce — 16 случайных байт, ciphertext — 16..4096 байт с 16-байтовым AEAD тегом.
AAD — не более 1024 байт, канонический UTF-8 JSON с точными полями:

```json
{"device_id":"raspb1","key_epoch":1,"sequence_number":1,"topic":"iot/sensors/raspb1","schema_version":2,"profile":"Ascon-AEAD128"}
```

Ключ выбирается из приватного DEVICE_REGISTRY_FILE, не из пакета/БД интерфейса.
Реестр связывает устройство, точный topic, единственную активную эпоху, уникальный
16-байтовый ключ и числовой Device_ID существующей БД. Publisher/smoke видят только
свои ключи; receiver/web — разрешённые устройства. Изменение AAD проверяется
AEAD тегом. Broker ACL дополнительно связывает учётную запись publisher с topic.
Принимается только iot/sensors/<device_id>, совпадающий с MQTT message.topic,
реестром и AAD. Отсутствующие/лишние поля, дубликаты JSON-ключей, NaN/Infinity,
неверные типы, bool вместо чисел/счётчиков и неизвестные профили отклоняются.

device_id — ASCII [A-Za-z0-9][A-Za-z0-9_-]{0,47}; sequence_number — целое
1..2^63-1, key_epoch — целое 1..2^31-1. Только активная provisioned эпоха допустима;
сменить эпоху сообщением невозможно. Старую эпоху отвергает реестр даже при
наличии корректного старого тега. Управление ротацией остаётся отдельной задачей.

Расшифрованный payload содержит ровно temperature, humidity, timestamp.
Температура — конечное число от -80 до 150, влажность — от 0 до 100. Timestamp —
ISO 8601 со смещением UTC; он используется только для отображения/правила задержки,
не как anti-replay. Неаутентифицированные метаданные разбираются только для выбора
разрешённого ключа/ограничений; до проверки тега нет записей БД или UI-событий.

## Постоянное состояние

Publisher резервирует sequence_number в SQLite (PUBLISHER_STATE_FILE) через
BEGIN IMMEDIATE и фиксирует его **до** шифрования/публикации. Файл 0600, каталог
volume 0700. Повторная доставка одного пакета сохраняет его sequence, а повторный
новый publish получает следующий. Пропуски допустимы. Не удаляйте state volume
при сохранении старого ключа: после утраты состояния требуется новая эпоха/ключ
и согласованное provisioning. Случайный nonce не выводится из сброшенного счётчика.

В PostgreSQL добавляется mqtt_replay_state с PK
(consumer, device_id, key_epoch) и last_sequence BIGINT. У receiver и web разные
фиксированные consumer-имена, чтобы два подписчика принимали исходный пакет
независимо, но не дублировали собственные эффекты. Вход разрешается только при
строго большем sequence_number. INSERT ON CONFLICT DO UPDATE ... WHERE
last_sequence < EXCLUDED.last_sequence RETURNING атомарен при конкурентных
подключениях; одновременно принять одинаковый пакет два раза нельзя.

Receiver держит replay update и INSERT аномалии **в одной транзакции**. Ошибка
INSERT откатывает счётчик, позволяя повторить пакет. Проверенные нормальные пакеты
тоже продвигают счётчик. Контейнерный restart не сбрасывает PostgreSQL volume.
Web фиксирует свой счётчик перед emit: повтор не рассылается вновь после рестарта,
но crash между commit и emit может потерять UI-событие. Exactly-once доставка
браузеру, outbox и многопроцессный Socket.IO здесь не заявляются.

Это high-water mark, не reorder-buffer: более старый пакет после нового
отклоняется даже при первом получении. Один упорядоченный producer на device;
несколько независимых publisher с одной identity требуют отдельного протокола.
Ни часы, ни флаг MQTT DUP не заменяют счётчик.

Схема создаётся аддитивно командой init-db: исходные 14 таблиц сохранены,
добавлена одна replay-таблица. Полная Alembic-переработка относится к этапу 5.
Криптографический reference код остаётся pure Python; constant-time/сертификация
всей реализации не утверждаются. Валидация протокола не зависит от assert/-O.

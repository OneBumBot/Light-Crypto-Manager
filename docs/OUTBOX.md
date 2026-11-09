# Transactional Outbox

`src/ingestion.py` принимает только `VerifiedTelemetry` после полного decode/AEAD
протокола v2. В одной транзакции PostgreSQL находятся конфигурация устройства,
PG device binding/enabled, условный replay upsert (`consumer=receiver`), аномалия при наличии причины,
`telemetry_outbox` и счётчик accepted. Ошибка любого INSERT откатывает всё.
`Sensor_Data` сохранена, но новый pipeline её не наполняет.

`src/outbox_relay.py` — отдельный процесс. `src/outbox.py` получает одну запись
через `FOR UPDATE SKIP LOCKED`, фиксирует token/lease/attempts, завершает PG
транзакцию, затем вызывает MongoDB. Базовая lease — 30 секунд, MongoDB операции
ограничены 5 секундами. Время lease берётся из PostgreSQL. Подтверждение/ошибка
принимаются только от текущего claim token. Старый worker после reclaim не может
переписать состояние нового. Несколько relay запускаются через `--scale
outbox-relay=2`; длительной PG транзакции при MongoDB IO нет.

MongoDB insert имеет journaled majority write concern (локальный standalone,
без репликационной отказоустойчивости). `_id` и unique compound key стабильны.
DuplicateKey — успех только после чтения и точного сравнения документа; разные
данные с тем же ключом — `TelemetryConflict`, доставка остаётся ошибочной.
BSON datetime округляется до миллисекунд до записи/сравнения.

Состояния: pending → claimed → delivered; ошибка → pending или dead. Начальная
пауза 1s, далее exponential backoff до 300s; максимум 12 claim попыток, включая
аварийно потерянные. После последней потерянной lease запись также становится
dead. При временной недоступности Mongo события сохраняются в PG; после
восстановления доставляются в следующую назначенную попытку. Длительный простой
может исчерпать попытки: dead не удаляются автоматически. После устранения
причины администратор может явно повторить конкретное событие:

```bash
docker compose --env-file .env.compose run --rm --no-deps outbox-relay --requeue-dead <EVENT_ID>
```

У relay нет HTTP API изменения журнала. `last_error` содержит только класс
исключения, а не payload/credentials. Outbox нельзя получить через table API.
PostgreSQL admin может исследовать status/attempts/available_at/lease_until,
не выводя payload; недоставленные записи никогда не очищаются автоматически.

## Очистка и backpressure

`OUTBOX_RETENTION_DAYS=0` по умолчанию отключает очистку. Явное положительное
значение включает удаление только delivered, максимум 1000 записей за итерацию.
Replay-state при этом сохраняется. До настройки retention PostgreSQL хранит
копию доставленной телеметрии: оператор должен выбрать срок и контролировать диск.
Dead/pending не удаляются. Минутные агрегаты ingestion_metrics не содержат
телеметрии, их автоматическая очистка пока отсутствует.

`MAX_OUTBOX_PENDING=100000` ограничивает сумму pending/claimed/dead. Admission
защищён PG advisory lock и точным count в той же транзакции: превышение не
продвигает replay. Повтор уже принятого пакета можно подтвердить и при полном
backlog. Receiver не имеет отдельной неограниченной Python очереди и не пишет
в MongoDB из MQTT callback: выполняет PG обработку последовательно.
Для QoS1 включены manual ACK и постоянная MQTT session с `MQTT_CLIENT_ID`
(по умолчанию lightcrypto-ingestion). ACK отправляется после PG commit или
классификации replay/invalid; при DB/backpressure ошибке соединение закрывается
без ACK, пакет повторяется после reconnect. Некорректный пакет подтверждается
для предотвращения poison-loop. Для нескольких receiver нужны разные client IDs;
high-water mark одного устройства по-прежнему предполагает упорядоченный producer.

Глобальная сериализация admission/count — сознательная текущая граница скорости,
а не доказательство 1000 msg/s. Backlog, PostgreSQL диск и брокерные очереди
конечны. MQTT PUBACK издателю означает приём брокером, а не PG commit. При
переполнении/утрате очереди брокера, потере volumes, откате replay-state/счётчиков,
потере ключей, диска или невосстановимом dead-event нет гарантии lossless.
Mosquitto persistence не заменяет репликацию/backup; аварийное выключение хоста
не равнозначно проверенным контролируемым restart.

## Границы доставки

Гарантия после успешного PG commit: durable intent + повторяемая **at-least-once**
попытка доставки с идемпотентным документом в период его хранения. Это не общая
атомарная PG/Mongo транзакция и не end-to-end exactly-once. Crash после Mongo
insert до PG ACK восстанавливается через lease и сравнение duplicate. Временная
недоступность PG оставляет QoS1 пакет без ACK; запас очереди брокера ограничен.
TTL MongoDB может удалить документ, после чего старая ручная redelivery способна
вставить его заново до следующей TTL очистки. Retention/backup согласуются отдельно.

Flask live MQTT остаётся независимым consumer=web: нет обещания replay-safe
exactly-once UI или атомарности Mongo истории и Socket.IO события.

API и первичные источники: [Alembic multiple metadata](https://alembic.sqlalchemy.org/en/latest/autogenerate.html),
[PyMongo driver](https://github.com/mongodb/mongo-python-driver).

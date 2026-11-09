# Схема телеметрии MongoDB

Обычная collection `telemetry.measurements`, **не time series**. MQTT v2 не менялся:
см. MQTT_PROTOCOL.md. `src/mongo_repository.py` формирует только явные поля из
проверенного сообщения; секреты и исходный registry туда не копируются.

| Поле | BSON / правило |
|---|---|
| `_id` | string `device_id:key_epoch:sequence_number`, стабильный ключ |
| `device_id` | ASCII 1–48, тот же provisioning ID, не числовой legacy DB ID |
| `key_epoch` | int32/int64, 1..2^31-1 |
| `sequence_number` | int32/int64, 1..2^63-1 |
| `measured_at` | BSON UTC datetime, из проверенного timestamp, миллисекунды |
| `received_at` | BSON UTC datetime, время приёма ingestion, стабильно при retry |
| `crypto_profile` | только Ascon-AEAD128 |
| `temperature` | конечное число -80..150 |
| `humidity` | конечное число 0..100 |
| `sensors` | пока строго пустой object; расширение требует версии контракта/валидатора |

Максимум BSON документа в репозитории 8192 bytes; серверная JSON schema запрещает
лишние поля, ограничивает типы/строки/диапазоны. Идентификатор не содержит ':';
склейка ключа однозначна. Даты в JSON outbox/API — ISO UTC; в MongoDB — Date,
PyMongo tz_aware=True. Секунды с большей точностью округляются вниз до миллисекунд.

Индексы: unique(device_id,key_epoch,sequence_number),
(device_id,measured_at desc,_id desc), (measured_at desc,_id desc), стандартный
unique _id. Сортировка стабильна для неизменного набора данных; offset-pagination
не является snapshot и может смещаться при одновременных вставках/TTL.

## Чтение

`GET /api/telemetry/history` требует активный login и существующее право
sensor_data (admin/operator/viewer). У пользователей пока общие права на все
устройства, отдельной tenant/device ACL в проекте нет. Параметры:
`device_id`, `start`, `end` (ISO UTC), `limit` 1..500 (100), `offset` 0..10000 (0).
Последние измерения: limit=N; последнее одного устройства: device_id=...&limit=1.
Ответ `{items:[],limit,offset}`, сортировка measured_at DESC + _id DESC.
Невалидные/повторные/неизвестные параметры → 400; нет входа → 401;
роль без права → 403; MongoDB недоступна → общий 503 без credentials/traceback.
Страница `/telemetry` использует эти же права и отображает строки через textContent.
Live dashboard не отключён и не является подтверждением Mongo commit.

## Retention

По умолчанию TTL **не создаётся**, автоматического удаления Mongo телеметрии нет.
Явная административная команда (например 30 дней):

```bash
docker compose --env-file .env.compose exec -e TELEMETRY_RETENTION_SECONDS=2592000 mongo mongosh --quiet --file /retention.js
```

Индекс TTL по received_at; 0 в этой же команде отключает существующий TTL, не
восстанавливая удалённые документы. TTL асинхронен, срок не точен до секунды.
Изменение срока может удалить старые данные — это явное действие оператора.
Роли relay/history не имеют права менять индексы/валидатор/delete.

Сравнение ordinary collection и time series — отдельный будущий эксперимент:
сопоставить write/read latency, размер, индексы, retention, cardinality и
восстановление после сбоя. Требование уникальности device/epoch/sequence и
ограничения time series на unique indexes требуют отдельного решения; заменять
основной маршрут до эксперимента нельзя.

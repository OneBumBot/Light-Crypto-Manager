# Асинхронный inference и гарантии

## Источник новых измерений

ml_observations создаётся в PG **после подтверждённой Mongo записи**, в acknowledge
транзакции relay. Это marker identity, без plaintext history/keys. Worker не сканирует
только measured_at и не использует unsafe high-water timestamp cursor. Он ищет
markers, для которых нет terminal event конкретного model_id/version. Поэтому
поздняя Mongo доставка старого measured_at и обратный порядок PG commit не теряются
из-за «уже пройденной даты». Изменение replay-state ради ML отсутствует.

Migration0004 backfills только retained delivered outbox, максимум100000 markers.
Уже очищенная до миграции история Mongo автоматически не backfilled. Для безопасного
cutover остановите старый relay, примените migration и запустите новый relay:
иначе старая версия relay может подтвердить запись без нового marker. Полная
историческая coverage до cutover не обещается; нужен отдельный controlled backfill.

Feed capacity=100000 в ml_feed_state. Пока ML выключен, markers остаются. При
заполнении основной pipeline продолжает delivery, счётчик overflow_skipped
увеличивается. Это явный gap, а не silent success/полная ML обработка. Capacity
может быть изменена только явной admin DB операцией с положительным значением.
Feed retention по умолчанию отсутствует. Явный CLI:

```bash
docker compose --env-file .env.compose run --rm --no-deps ml-worker --prune-feed-days 30
```

Удаляется до1000 старых markers за вызов; existing scored events сохраняются
(FK SET NULL), незавершённые получают feed_expired. Делать при остановленном worker;
это явная утрата возможности автоматического backfill новых моделей. pruned/gap
counters сохраняются. Ни replay-state, ни Mongo measurements CLI не удаляет.

## Claim / обработка

- Короткая PG transaction: FOR UPDATE SKIP LOCKED marker + fresh event row lock,
  claim token и lease30s. Повторно завершённый результат не перезаписывается из-за
  старого outer-join snapshot. Завершение fenced по token/status.
- Вне PG transaction: Mongo find target identity и максимумN previous sequences
  того же device/epoch по existing unique index. Проверяются времена; future
  measured/received values не участвуют в расчёте, некорректное окно пропускается.
- Causal features → frozen pipeline → score → одна PG запись. Unique key:
  device_id/key_epoch/sequence_number/model_id/model_version. Разные модели/версии
  независимы; повторный расчёт при crash возможен, duplicate event отсутствует.

Нет end-to-end exactly-once. Lease/retry обеспечивают восстановление в пределах
сохранённого feed и доступных Mongo документов. Если предшествующая Mongo запись
ещё не видна из-за late relay, оценивается текущий bounded snapshot: warmup/
skip является сохранённым результатом, автоматического пересчёта terminal event
после пополнения окна нет. Это граница completeness, не использование будущего.

При Mongo outage/не видимом или истёкшем source: status retry, attempts и backoff2,
4,..до256s (cap300), максимум8 attempts, затем dead. Прежние корректно committed
ML events не стираются. DB failure оставляет processing lease для последующего
reclaim. Ошибки не содержат raw payload/credentials. Skips: warmup, unknown_device,
out_of_order, invalid_history; score/flag=null, они не означают «нормальное».

## Модель / отключение

Model root задан явно, локальные manifest/hash/versions проверяются до unpickle.
Network model не допускается в online telemetry worker. ml_models фиксирует
artifact и manifest hash для immutable model_id/version. Heartbeat/stale (>30s)
и available/unavailable/disabled/version_conflict доступны через API.

ML_ALLOW_RESEARCH по умолчанию0, профильml не включён. Без ML receiver/relay/Mongo
работают. Отсутствие артефакта даёт unavailable и retry load, без auto-training или
подмены random dataset. Даже после opt-in все модели DEMO/RESEARCH, не доверенные
attack detectors; ML не меняет cryptographic profiles или MQTT commands.

## API / UI / метрики

`GET /ml`, `/api/ml/events?device_id=...&limit=50&offset=0`, `/api/ml/status`
требуют login и прежнее право sensor_data. Events limit1..200, offset0..10000;
строки сортируются по evaluated_at/id. UI — DOM textContent, не innerHTML; тяжелой
inference внутри HTTP нет. Unknown/inactive role не проходит login loader.

Protocol reject count виден только admin, rule count — при доступе к anomalies;
ML events доступны ролям с sensor_data. Эти источники не объединяются в «атаки».
Scores/threshold/version/status/время показаны отдельно, mode явно Research/Demo.

prepare_ms/inference_ms измеряются monotonic clock; delivery_ack_lag_seconds —
от PG confirmation Mongo write до оценки. Это не точное время первого disk insert
(после повторной доставки может быть раньше ACK). Counts — текущие статусы событий,
не cumulative attempt rates; attempts отдельно в PG. API aggregates пока по всему
retained journal, не оптимизированы под1000msg/s. Внешние monitoring/alerts/HA и
нагрузка10000 устройств не реализовывались.

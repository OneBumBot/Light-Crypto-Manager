# Две базы данных — этап 5

PostgreSQL — управляющие данные и источник истины anti-replay. MongoDB — только
проверенная история измерений. Общей транзакции между ними нет: для доставки
используется PostgreSQL Transactional Outbox (см. OUTBOX.md).

MongoDB — официальная 8.0.17 с digest, без опубликованного порта, постоянный
volume. Отдельные роли: relay может только insert/find measurements, web — find.
Root используется только при инициализации и администрировании/healthcheck.
Пароли: `python3 scripts/prepare_storage.py --directory .local-runtime/mongo-security`.
Добавьте `MONGO_SECURITY_DIR` в приватный env Compose. Старые PG volumes не удалять.
`storage-init` копирует материалы с 0700/0600 в отдельные volumes сервисов.
При повторном запуске MongoDB init scripts не меняют существующую БД/пароли:
для ротации необходима явная административная операция.

## PostgreSQL migrations / control registry

`src/migrate.py` запускает Alembic под PG advisory lock. 0001 — frozen legacy
snapshot + валидация, 0002 — outbox/metrics, 0003 — telemetry_devices. Metadata
собирается из ORM, replay, outbox и device Core tables; составные PK legacy не
меняются. Нет drop_all, автоматического destructive downgrade или blind stamp.
Существующие таблицы/данные/replay сохраняются. Проверены empty/legacy/repeat/
incompatible сценарии на независимых тестовых схемах.

telemetry_devices хранит device_id → numeric legacy ID/topic/profile/active epoch,
включая enabled, без ключей. Реестр согласуется явным provisioning с приватным
key registry; конфликт не перезаписывается. Consumer проверяет обе привязки до
replay/admission. Выключение в PG блокирует и ingestion, и live consumer. Ротация
требует явного согласованного изменения PG/key-registry/ACL; автоматизации пока нет.
14 legacy таблиц, replay, outbox, metrics, devices и alembic_version — 19 таблиц.
Legacy конфигурация/история остаются в Device_Configuration, существующие
числовые ID не переименовываются. FK к составным legacy ключам не добавлены.

## Будущие измерения масштабируемости

Цели: 100/1000/5000/10000 устройств с периодом10s → 10/100/500/1000 msg/s. Это
план экспериментов, не результат этапа5. Сравнивать одинаковые message sizes,
периоды/ключи/эпохи, TLS/ACL, hardware/volumes и прогрев; снимать PG commit latency,
CPU/RAM/диск, outbox age/depth, Mongo write/history p50/p95/p99, reject/retry/dead,
восстановление после отключений. Независимые device identities/keys/topic ACL
обязательны; общий анонимный ACL/общий ключ недопустим. Текущий admission lock,
точный count backlog и один callback — известные ограничения; batch/counter
оптимизации сначала требуют сохранения атомарности и измерений. Сравнение ordinary
и time series Mongo коллекций выполняется отдельно с проверкой идемпотентности.

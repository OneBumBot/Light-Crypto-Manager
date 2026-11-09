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

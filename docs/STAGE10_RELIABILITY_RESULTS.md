# Stage10 reliability: наблюдения и пределы

Результаты реальных отказов сохраняются в `reports/stage10/reliability-10.json`, настоящие DOM/HTTP/MQTT recovery — в `browser-10.json`; для25 устройств отдельные switching/browser artifacts. Каждый fault запускается последовательно, только новый performance project; before/during/after SQL counters, backlog и effective evidence сохранены. Фиксируется начало и возврат сервиса, hold и время наблюдаемого drain. Время docker start входит в total, post_start_recovery отдельно. Это не абсолютная availability guarantee.

Проверки: Mongo outage накапливает Outbox, PG admission продолжается, потом drain; control/policy outage не останавливают crypto telemetry, heartbeat stale, effective не выдумывается; PG outage API503, durable volume тот же; broker outage reconnect; device restart выдаёт новый sequence grant; receiver restart сохраняет persistent session и unique admission. Вне специальных poison/replay проверок рост replay может означать QoS1 redelivery и не называется атакой.

Условия переключения неизменны: adminHTTP+CSRF → committed intent → PREPARE/READY → ACTIVATE → authenticated response → AEAD telemetry receipt. HTTP202 и ACK отдельно от effective. Timestamp rows/commands берётся из PostgreSQL, не client status. Не измеренные стадии не заменяются наблюдаемой HTTP длительностью. Полная command/ACK wire/keys в отчёты не экспортируются.

Сравнение accepted и Mongo выполняется после bounded drain; pending != loss. Исходная source population берётся из agent journal там, где он доступен, иначе not_measured. PostgreSQL commit failures по-прежнему не превращаются в invalid telemetry и не ACK-аются receiver как успех. Дополнительные настоящие poison/recovery probes и regression фиксируются отдельно.

# Stage10 reliability: наблюдения и пределы

Результаты реальных отказов сохраняются в `reports/stage10/reliability-10.json`, настоящие DOM/HTTP/MQTT recovery — в `browser-10.json`; для25 устройств отдельные switching/browser artifacts. Каждый fault запускается последовательно, только новый performance project; before/during/after SQL counters, backlog и effective evidence сохранены. Фиксируется начало и возврат сервиса, hold и время наблюдаемого drain. Время docker start входит в total, post_start_recovery отдельно. Это не абсолютная availability guarantee.

Проверки: Mongo outage накапливает Outbox, PG admission продолжается, потом drain; control/policy outage не останавливают crypto telemetry, heartbeat stale, effective не выдумывается; PG outage API503, durable volume тот же; broker outage reconnect; device restart выдаёт новый sequence grant; receiver restart сохраняет persistent session и unique admission. Вне специальных poison/replay проверок рост replay может означать QoS1 redelivery и не называется атакой.

Условия переключения неизменны: adminHTTP+CSRF → committed intent → PREPARE/READY → ACTIVATE → authenticated response → AEAD telemetry receipt. HTTP202 и ACK отдельно от effective. Timestamp rows/commands берётся из PostgreSQL, не client status. Не измеренные стадии не заменяются наблюдаемой HTTP длительностью. Полная command/ACK wire/keys в отчёты не экспортируются.

Сравнение accepted и Mongo выполняется после bounded drain; pending != loss. Исходная source population берётся из agent journal там, где он доступен, иначе not_measured. PostgreSQL commit failures по-прежнему не превращаются в invalid telemetry и не ACK-аются receiver как успех. Дополнительные настоящие poison/recovery probes и regression фиксируются отдельно.

Итоговый полный source census (`fault-source-census.json`, `fault-source-intervals.json`) сопоставил все 26 607 сохранённых formed events двух fault-cohorts с PG; missing identities0. По семи интервалам остановки/возврата сервиса: 481,346,781,240,33,226,210 formed — все приняты после восстановления. Journal не fsync-authority: несохранённое событие при произвольном crash не учитывается. В полном журнале десяти агентов20 reconnect того же процесса (включая browser broker outage), а stop/recreate отдельно. DB reconnect count not_measured.

## Семь последовательных реальных отказов

Интервал source census начинается до команды stop и заканчивается после возврата сервиса; он не равен только искусственной hold-паузе. Время восстановления ниже — наблюдаемый post-start drain, не точный service RTO.

| Сервис | Hold, с | Post-start drain, с | Formed в интервале | Найдено в PG после восстановления | Неподтверждено |
|---|---:|---:|---:|---:|---:|
| mongo | 12 | 15.48 | 481 | 481 | 0 |
| control-worker | 12 | 34.21 | 346 | 346 | 0 |
| policy-worker | 32 | 10.77 | 781 | 781 | 0 |
| postgres | 8 | 24.84 | 240 | 240 | 0 |
| broker | 8 | 1.33 | 33 | 33 | 0 |
| device-alpha | 5 | 17.71 | 226 | 226 | 0 |
| receiver | 5 | 6.07 | 210 | 210 | 0 |

Дополнительно девять существующих control recovery scenarios прошли: `control-recovery-extended.json`. Poison Ascon/AES —17 rejected каждый, последующие valid/neighbor accepted; explicit receiver restart не дал poison redelivery.27 mutations выявлены поведенчески; final pytest739 passed/0 skipped/exit0. Итоговые38/38 crypto transitions подтверждены AEAD receipts, pending/dead/unknown0.

После shutdown35 durable pending Outbox записей доставлены при resume только storage/relay без новых admissions (`shutdown-outbox-resume.json`). Named volumes/keys сохранены, `down -v` не выполнялся. Все четыре проекта остановлены: `shutdown-final.json`.

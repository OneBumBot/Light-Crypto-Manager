# Этап 13: измерение Policy throughput

Исходный controller: `649a80ff7f7d66f72f5f483b384754ae594f221e`. Оптимизированный runtime зафиксирован в image до серии; точные image IDs, worker/state/engine hashes, rules SHA, hardware, schema/settings и команды находятся в каждом `result.json`. Более поздний host HEAD не подменяет происхождение уже собранного image.

Один cohort за раз; Policy 1 CPU/256 MiB, PostgreSQL 1 CPU; software agents 2 Hz, настоящие MQTT/TLS, AEAD, PG admission и Outbox/Mongo. Не сравниваем увеличение ресурсов с ускорением кода. Initial history/разброс startup реальных cohorts не полностью одинаковы и записаны явно. Дополнительные matched SQL/FSM ablations используют идентичную историю/поток, но не выдаются за сетевую телеметрию.

| Устройства | Прогон | Входящие source observations | Обработаны в интервале | Pending на рабочем снимке | Pending после bounded drain |
|---|---|---:|---:|---:|---:|
|3|baseline|1798|1800|3|0|
|3|optimized|1797|1800|3|0|
|10|baseline|5999|5989|17|0|
|10|optimized|6005|6018|1|0|
|25|baseline r1|15004|7520|7796|1547|
|25|baseline r2|15009|7514|7817|1495|
|25|baseline r3|15004|7488|7838|1500|
|25|optimized r1|14998|14996|16|0|
|25|optimized r2|15110|15102|9|0|
|25|optimized r3|15069|15037|43|0|
|25|optimized 15 минут|44827|44801|36|0|
|50|baseline|31231|7355|25006|18721|
|50|optimized|30940|30940|2|0|

Основные прогоны номинально 300 секунд; стабильность 900 секунд. Таблица использует **разность двух SQL snapshots**: их интервал включает отдельные probes и может быть длиннее observation window. Например, optimized50: 30940/309.691544 ≈99.9 observations/s, а не 30940 за ровно300 секунд. Processed может превосходить incoming из-за initial pending; сохранение проверяется `pending_end=pending_start+incoming-processed`. Scheduled/formed/publish/queued/PUBACK/PG/Mongo — отдельные счётчики. PUBACK не служит доказательством PG commit.

Baseline25 обрабатывает примерно25 events/s при поступлении около50/s; baseline50 также отстаёт. Его bounded drain не завершён, остаток durable; такой прогон не объявляется успешной своевременной обработкой. Непроцессированные события имеют censored latency, а не нулевую задержку. Оптимизированный controller поддерживает фактический входящий поток25/50 устройств в измеренной среде; это не универсальный предел мощности и не HA-гарантия.

Три независимых 25-device repeats — основное сравнительное основание. По одному 3/10/50-device run и один 15-минутный run характеризуют только проверенную среду. Packet percentiles коррелированы внутри run; confidence intervals из них не строятся. PG connection/lock/transaction counters включают ingestion, relay, web и измерительные probes. SQLAlchemy hooks не видят server-internal queries и pre-ping.

Отдельная короткая paired серия измеряет monotonic wall реального `engine.begin()` от checkout до успешного commit exit. Она не является точным серверным SQL/fsync временем. После ручной остановки и восстановления Codex два незавершённых r3 исключены; их partial artifacts сохранены. Docker address pool исчерпан; только новые продолжения получили непересекающиеся /24 подсети, старые сети/volumes не удалялись.

Полная сводка, исходные идентификаторы и графики: [reports](reports/stage13/), `performance-summary.json`, `run-summary.csv`, `figures/`. Итоговая сверка использует независимый journal↔signals anti-join и formed identity↔PG Outbox↔Mongo, а не только размер новой очереди. Присутствие файла/строки PASS само по себе не заменяет assertions.

## CPU/RAM, задержка и цена транзакций

Три25-device repeats: baseline Policy CPU mean6.12–7.66%, RSS mean41.14–41.45MiB; optimized9.53–10.83%,40.76–41.40MiB. Ускорение потребляет больше полезного CPU, не сопровождается непрерывным ростом RAM в этих снимках.15-минутный run mean9.68%/40.83MiB.50-device optimized18.73%/40.50MiB. Это sampled Docker utilization, а не профилирование всех аллокаций/доказательство отсутствия утечек.

Conditional inflight source→processing p95 baseline25:147.54/148.08/148.85s, optimized0.956/0.959/0.963s; baseline pending остаются censored. Optimized15min p950.960s;50 p950.941s. Околосекундная свежая задержка совместима с idle polling1s; дальнейшее event-driven wakeup не реализовано. Events могут стать поздними из-за задержки baseline; сравнение фактических decisions с разными evaluation times не является golden equivalence.

Client SQL hooks/source attempt в live25: baseline11.406, optimized9.164–9.188; controlled batching7.202 (без startup/heartbeat). Один live batch не обязан содержать32 события. Matched cached/uncached абляция показывает ровно один сэкономленный Rules SELECT/event. Application processing commits на1000 synthetic sources уменьшаются1000→32; это не число всех server transactions.

Две корректные короткие paired25-device серии: baseline admission transaction wall median3.692/3.730ms, optimized3.752/3.704ms; p95 baseline5.154/5.951ms, optimized5.864/5.193ms. Наблюдаемого существенного систематического ухудшения median нет; две независимые пары и scheduler noise не доказывают строгую equivalence границ tail latency. Correlated per-packet p99 хранятся в JSON, без необоснованного CI.

Суммарно в17 включённых runs232843 PG admissions и232843 соответствующих Mongo records; это whole-run census, включая startup/drain, не сумма только300s окон. Отдельные исключённые recovery runs сохраняются для аудита и не включены в эту цифру.13 семейств PNG/SVG строятся из фактических summary/ablation/golden данных.

# Этап 15 — пассивный Shadow IDS: результаты

## Итог и исходное состояние

Инженерный pipeline реализован: настоящий пассивный захват MQTT/TLS, streaming extraction, проверенные замороженные RF/IF, отдельный durable journal и read-only UI. Научный verdict: **INDEPENDENT_GENERALIZATION_NOT_VERIFIED**; новая оценка переносимости — **BLOCKED_INDEPENDENT_DATA**. Один host и короткие программные опыты не доказывают пригодность реального IDS. Плохие результаты IF сохранены без изменения порога.

Исходная ветка `feature/rf-if-ground-truth-validation`, SHA `6903802c7a2267c890c739f2dce7122926950382`. Итоговая ветка `feature/online-shadow-ids-validation`; финальный SHA указан в Git и итоговом сообщении. Main не менялся, push/merge/rebase не выполнялись. [Все изменённые файлы](reports/stage15/changed-files.txt). Baseline: **967 passed, 0 skipped, 52.99 s, exit 0**. Alembic head: `0011_policy_throughput`; новых миграций нет.

## Компоненты и изоляция

Код расположен в `src/shadow_ids/`: `capture.py`, `pcap.py`, `features.py`, `models.py`, `worker.py`, `journal.py`, `sessions.py`, `web.py`, `isolation.py`, `frozen.json`. Capture и inference — отдельные процессы. Они не импортируют offline training/oracle для вычисления score. Обычный receiver продолжает самостоятельно проверять AEAD и фиксировать PostgreSQL admission/Outbox.

Capture point: `lab-devices` network namespace, `eth0`, оба направления TCP/8883 внутреннего брокера. Ограниченный tcpdump пишет classic PCAP и передаёт реальные кадры streaming reader. Контейнер получает только NET_RAW поверх cap_drop=ALL, без privileged, Docker socket, внешнего порта, key registry, MQTT/HMAC credentials или TLS decryption keys. Model worker работает с network=none, без capabilities, с read-only root и approved model mount. Web получает только journal-only read-only mount. Доступ к журналу: directory 0750, SQLite/WAL/SHM 0640, отдельная supplementary group; PCAP, модели и ключи остаются приватными 0600/0700 и web не монтируются.

Заданы ограничения CPU/RAM/pids/logs, 20 000 packets, 32 MiB capture, 512 pending events, 50 000 journal events, 1024 flow states и длительность capture 3–60 s. Перед стартом проверяется свободный диск, затем действует disk watchdog. Пропуски не маскируются. Перезапуск crypto/nonce authority из Shadow невозможен.

Созданы отдельные `lcm-stage15-shadow-ids-baseline`, `online`, `regression`: новые CA, credentials, telemetry keys, PG/Mongo volumes, counters и Shadow SQLite. Старые volumes не подключались. Used-volume guard блокирует неявный старт пустого state со старыми ключами. Все новые сервисы после испытаний остановлены, данные сохранены.

## Пять признаков и TCP generations

Схема `tcp-packet-passive-v1`, фиксированный порядок:

1. `frame.len`: исходная длина Ethernet frame, не длина sensor JSON.
2. `tcp.len`: длина TCP payload, включая непрозрачные TLS bytes.
3. `tcp.flags`: точное числовое представление, включая NS; reserved bits отклоняются.
4. `tcp.window_size_value`: raw 16-bit window, без window scaling.
5. `tcp.time_delta`: разница kernel capture timestamps соседних пакетов одной двунаправленной TCP generation.

У первого initial SYN delta=0 по определению, а не в результате заполнения неизвестного времени. Состояния разных flow разделены. Initial ISN, SYN retransmission, FIN/RST, tuple reuse, sequence continuity/wraparound, expiry и LRU учитываются. Missing SYN, capture mid-session, negative timestamp, forward sequence gap и потеря контекста не дают обычного score. Более ранний SYN не может незаметно начать новую полную сессию. IPv6, fragmentation, VLAN/PCAPng и переносимость offload behavior не объявлены поддерживаемыми.

Три итоговых parity captures: **327 + 324 + 324 = 975 packets**. Совпали 3900 целочисленных feature values; все 975 delta уложились в заранее заданные 1.1 μs, mismatches=0. Проверены реальные frame SHA-256 identities, независимый offline parser и tshark. Четыре повреждённые копии actual sources отвергнуты, в том числе согласованное изменение PCAP и metadata hashes. Это отрицательные копии, не новые независимые captures.

Реальный tuple reuse: два MQTT/TLS соединения с теми же endpoints/port, 34 packets, два PostgreSQL admissions; обе новые generation имеют first delta=0. С tshark расхождений нет. Старый `pcap_audit.headers` использует tuple-global delta и имеет **одно расхождение на границе reuse**; он не переписан. Это ограничение старого extractor, явно отделённое от основной parity. [Подробный контракт](STAGE15_FEATURE_PARITY.md).

## Замороженные модели и session aggregation

Использованы только выбранные на Stage14 validation артефакты версии 14.0.0:

| Назначение | Model ID | Packet threshold | Session rule/threshold |
|---|---|---:|---|
| Packet RF | research75-rf_tuned_1-binary | 0.9335469686522243 | Не является выбранной session-моделью |
| Packet IF | research75-if_tuned_0-binary | 0.5971711560322518 | Не является выбранной session-моделью |
| Session RF | research75-rf_subsample-binary | 0.9 | mean / 0.19333333333333336 |
| Session IF | research75-if_tuned_1-binary | 0.652579820387762 | fraction / 0.10344827586206896 |

Artifact/manifest SHA, provenance, owner/permissions, model/feature/preprocessing versions, package versions и thresholds проверяются по packaged pins и оригинальному freeze. Joblib загружается только из разрешённого приватного хранилища: hash сам по себе не делает произвольный pickle доверенным. Оригинальный freeze SHA: `c8dccff4bbd36c8346269c60045af04f02d3d70974f5754b7732fd172332fc40`.

На 128 **новых** packet vectors выполнено 512 точных сравнений online score с исходной offline formula: maximum difference=0. RF использует 1−P(normal), IF — исходный score_samples mapping; score не назван вероятностью атаки. Features ровно пять; IP/ports/session/scenario/PG category не predictors. Fit, refit, retuning, calibration и Model Registry install: **0**. Старый holdout не использовался для нового выбора или обучения.

Session counters обновляются только вместе с первым committed prediction. Промежуточные mean/max/fraction используют только уже наблюдённые пакеты и не backdate результат. Final observed-capture view отделён от final TCP-session result: без полной capture, начального SYN, корректного контекста и двустороннего FIN либо RST сессия остаётся partial. Все supported online packets и Stage14 purged known subset — разные популяции; прежние offline metrics не переносятся автоматически.

## Durable journal, attribution и UI

Отдельный SQLite WAL/FULL хранит events, outcomes и session counters. Unique event/run ordinal и (event, model) обеспечивают идемпотентность. Batch не более 64 results, `BEGIN IMMEDIATE`, ограниченные busy retries и atomic commit results/processed marker/session counters. Rollback не оставляет partial processing. Infrastructure error, invalid score или отсутствующая модель дают явный статус с null, а не score=0/Normal. Latency journal commit измеряется после возвращения commit; отсутствующее timing evidence не заменяется нулём.

Все результаты имеют `mode=SHADOW_ONLY`, `trusted_detector=false`, `device_binding=unbound`. Network Session Identity не превращается в authenticated device identity по IP/port. Wrong-password connection не получает вымышленный device_id. Привязка к физическому IoT не заявлена.

Read-only `/research/shadow-ids` и `/api/research/shadow-ids` используют существующий Flask/RBAC, bounded pagination, same-origin, no-store и escaping/textContent. Нет кнопки применения профиля и score не показан как вероятность атаки. Различаются heartbeat, traffic, backlog, drops, model unavailable, source freshness. Freshness зависит также от **capture timestamp последнего обработанного evidence**, а не только heartbeat/времени записи результата. Старые rows помечаются STALE; при source/PG unavailable текущий snapshot очищается. Настоящий Chromium проверил отображение scores, запрет POST, XSS, no-store, source expiry и очистку при реальном PG outage. Внешний порт не публиковался.

## Настоящие нагрузочные измерения

Матрица заранее зафиксирована: 3 устройства × 0.5 Hz, 10 × 1 Hz, 25 × 2 Hz, 50 × 2 Hz. Четыре условия: observer off, capture only, RF, RF+IF. По три условных повтора, всего **48 успешных runs**, workload около 15 s/run. Один host/realm, разные TLS sessions/ключевые состояния; это не независимые hardware domains и не доказательство steady-state capacity. Cohort — software identities/Paho threads bounded producer, не 50 физических устройств и не 50 отдельных Control Agent containers.

Итог успешной серии: **24 483 formed = queued = PUBACK = PG committed = Mongo delivered**. Точное сравнение (device, epoch, sequence), не совпадение aggregate counters. **68 751 captured TCP packets**, **69 492 SCORED rows**; inference rows считаются по модели, поэтому это разные единицы. Captures complete, kernel/reader/application drops=0, final pending=0, Outbox после drain=0. Scheduled publications не инструментированы в event-driven loop; плановое число нельзя выдавать за фактически отправленное.

| Cohort | PG/s off | capture | RF | RF+IF | Среднее run-median capture→prediction, RF / RF+IF |
|---|---:|---:|---:|---:|---:|
| 25 × 2 Hz | 44.75 | 44.55 | 44.68 | 44.47 | 0.760 / 0.795 s |
| 50 × 2 Hz | 80.33 | 69.89 | 74.84 | 75.92 | 0.954 / 0.958 s |

Фактические 100 telemetry admissions/s не достигнуты. Нельзя объявлять отсутствие влияния observer или выводить строгий причинный эффект из коротких same-host runs. Libpcap buffering заметен в soft latency порядка секунды; hard real-time не доказан. CPU, sampled container memory, отдельный ru_maxrss, p50/p95/p99, batch time, source lag и Outbox timings сохранены в JSON/CSV и семи семействах графиков. Container MemUsage не переименован в точный RSS. Resource samples обрезаны по реальному workload window. [Результаты и графики](STAGE15_PERFORMANCE_RESULTS.md).

Дополнительный 25-device queue probe: 3283 captured packets, complete/kernel drops=0; sampled maximum pending **188/512** при опросе 0.5 s. Наблюдение между samples не известно. Это диагностический опыт, не четвёртый независимый повтор. Four-model E2E: **89 PG/Mongo admissions, 321 packets, 1284 SCORED rows**.

## Operational labels, QoS1 и ложные срабатывания

Выполнены 13 contrast cases с реальными PCAP, broker logs, независимым witness и PG evidence: regular/jitter, QoS1, replay, wrong epoch/sequence, tampered tag, ACL denial, bad credentials, bounded rate, pattern change, reconnect, receiver restart. Oracle и builder не заменены inference. Двенадцать evidence views прошли проверку; broker reconnect потерял witness и quarantined — FPR не вычисляется. В валидированных views: 1154 Normal, 145 ControlledViolation и 681 Unknown observation (34.39% unknown); packet rows не равны независимым sessions.

Для трёх corroborated normal controls доступны **375 Normal observations и 12 activity sessions/windows**. Packet RF: **0/375** false threshold crossings; packet IF: **254/375 = 67.73%**. Выбранные session RF: **0/12**, session IF: **12/12** false window aggregates. Ноль в небольшом sample не доказывает нулевой operational FPR. Window labels не являются packet-specific malicious attribution и не гарантируют full closed-session completeness.

QoS1 не переименован в атаку. Replay и транспортный retry могут быть неразличимы по пяти признакам. Wrong epoch/sequence и tampered actor без достаточной независимой корреляции остаются unknown. Backend replay verdict не добавлялся в predictors. На unlabelled нагрузочной серии FPR=`not_evaluable`, отдельно доступен shadow alert rate. Нормировка короткого run на час — rate estimate repeated threshold crossings, не наблюдённый час и не число независимых инцидентов. [Operational report](STAGE15_OPERATIONAL_FALSE_POSITIVES.md).

## Найденные дефекты и восстановление

1. Первый минимальный model image через offline helper импортировал Research Stand и получал ModuleNotFoundError. Rows были INFERENCE_ERROR/null. Негодная серия остановлена и сохранена. Узкая formula не импортирует training/oracle; 512 exact cross-checks подтверждают совместимость.
2. Первый 25-device RF run выявил SQLite writer contention и падение worker. Получены 2544 physical packets, kernel drops=0, но application overflow=1767: это CAPTURE_INCOMPLETE, не lossless success. Все **697** сформированных telemetry identities сохранены в PG/Mongo. Исправление — bounded atomic batch/retry, без снятия лимитов. Полная успешная 48-run серия повторена отдельно; failed runs не включены в неё.
3. Усилены проверки JSON types, преждевременного SYN, processed-evidence freshness и causal session closure. Ошибки экспериментальных tuple/browser harness сохранены, не выданы за криптографические дефекты. Legacy DOM-XSS fixture обновлена под уже существующий Stage13 diagnostic contract; старые XSS assertions сохранены, Policy JavaScript/FSM не менялись.

Реальные fault tests: observer/model SIGKILL и restart, broker/PG/Mongo outages, receiver restart, missing model, wrong hash/version, bounded overflow, disk floor. Отдельно проверен настоящий OOM при 6 MiB (exit 137/OOMKilled=true): receiver принял ещё 36 telemetry records, Mongo доставила их, Outbox=0, raw evidence сохранено. 16 MiB case не вызвал OOM — он не засчитан как kill. Disk watchdog проверен на отдельном 1 MiB tmpfs, host disk не заполнялся. После lost SYN/context recovery неполная сессия не объявляется нормальной. Broker outage может остановить bounded producer; lossless continuous outage recovery не заявлен. [Reliability matrix](STAGE15_RELIABILITY_RESULTS.md).

## Регрессия, сохранность и границы доказательств

Финальная полная регрессия: **1049 passed, 0 skipped, 56.64 s, exit 0**, отдельные реальные PG/Mongo. Финальный code/test source: `7558f410a78a41535a3f36cd3923244dff311d80`, readonly source/test bindings в существующий test image явно записаны в report. Source основной performance серии: `dd3d15a7b141918188214a25af74f6d3ba97cff3`; последующие дополнительные guards проверены отдельно, полная performance-матрица за них не выдана. **31/31** mutation defects обнаружены по поведению, не SyntaxError/ImportError. Ascon/AES/Kuz KAT, nonce/replay, HMAC/manual control, receipts, Outbox/Mongo, RBAC/CSRF, Policy13 traces/throughput и Stage14 oracle/frozen lifecycle сохранены.

Финальный online realm: **32 845 PG = 32 845 Mongo records**, все Outbox delivered; duplicate identities=0. Security journal: accepted 32845, replay 15, rejected 36, delivery_delay 30; overflow=0. Live control commands/transitions, registered ML models, ML anomaly events, Policy signals/applied states: **0**. Это дополнительная проверка отсутствия бокового канала, не подтверждение производительности работающего Policy Worker в этом стенде.

Новый Stage15 network workload использовал **Ascon**. AES/Kuz проверены прежней полной регрессией; новых live AES/Kuz/manual switching experiments Stage15 не заявляет. Криптографический протокол, nonce/key authority, HMAC control, Policy FSM/worker, Outbox и независимый label oracle byte-equal исходному HEAD. Policy остаётся **DRY_RUN**, control — **MANUAL_AUTHORIZED_CONTROL**, RF/IF — **trusted_detector=false**. Kuznyechik lab-only, Magma не добавлялась.

До/после сверены **1322 защищённых tracked files и 5592 private artifacts**, старые migrations/reports/PCAP/CSV/models/plans/SQLite и метаданные старых Docker projects/volumes; старые сервисы не перезапускались. Это не чтение содержимого старых SQL volumes. Secret audit проверяет exact generated secrets в public files, application image /app и последних 1000 log lines/container; граница сканирования явно указана, это не формальное доказательство отсутствия любых секретов. PCAP/joblib/keys не включены в Git. [Preservation](reports/stage15/preservation-after.json), [security](reports/stage15/security-release.json), [команды и exit codes](reports/stage15/execution-summary.json). Для pytest сохранены точные Docker command arrays; для остальных harness — нормализованные top-level invocations и actual argv/exit states остановленных keyless контейнеров. Не каждый вложенный docker exec или shell redirect был сохранён дословно.

Другого физического host нет: `independent_host_domain=not_verified`, новый scientific final holdout не объявлялся и не открывался. Development shortcut audit выполнен до новых contrast views; он не заменяет достаточный independent-domain dataset. Разрешены утверждения о проверенной локальной feature parity, работе frozen inference и границах operational results. Не доказаны внешняя переносимость, обнаружение реальных атак, physical IoT/ARM, production eligibility, hard real-time или whole-provider constant-time.

## Воспроизведение и следующий этап

```bash
.venv/bin/python -m scripts.stage15_setup prepare --directory .local-runtime/stage15/new-demo --project lcm-stage15-shadow-ids-newdemo --subnet 10.215.10.0/24
.venv/bin/python -m scripts.stage15_setup start --directory .local-runtime/stage15/new-demo --build
.venv/bin/python -m scripts.stage15_runs parity --directory .local-runtime/stage15/new-demo --prefix new-parity --output .local-runtime/stage15/new-demo/feature-parity.json
.venv/bin/python -m scripts.stage15_performance sanity --directory .local-runtime/stage15/new-demo --series unique-new-demo
.venv/bin/python -m scripts.stage15_setup stop --directory .local-runtime/stage15/new-demo
```

Start не разрешает inference до PASS, привязанного к текущему extractor hash. Новые run IDs/paths обязательны; raw evidence и старые reports не переписываются. Private Stage14 approved artifacts требуются локально; они не скачиваются и не поставляются с Git.

Для отдельно разрешённого этапа 16 рекомендуются другой host/day/domain, prospective shortcut audit, длительный shadow-only soak, проверенные normal controls и новые labels. Любая calibration — отдельный preregistered development/holdout experiment. Автоматическое управление криптографией не включать. Этап 16 не начинался.

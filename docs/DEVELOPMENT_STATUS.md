# Этап 10 — измерения и подготовка расширения

Ветка `feature/system-performance-validation`, исходный SHA `4ac5081a69199041fb8e34111b976da6c257ac93`.
Полный baseline после UI: 715 passed. После изменений: 739 passed, 0 skipped;
реальные browser/TLS/PG/Mongo и recovery, 27 выявленных поведенческих мутаций.
Данные, команды, exit codes и ограничения: [STAGE10_RESULTS.md](STAGE10_RESULTS.md).

Проверены 3/10/25/50 программных устройств, 15 минут для 25 и 5 минут для других
основных cohorts. Telemetry path работает на 50×2 Гц; Policy при 25/50 отстаёт.
Исправлены HTTP503 при недоступной БД загрузки identity и отображение старого
Policy evidence как свежего; FSM/криптопротоколы не менялись. Есть план ГОСТ,
но новых активных алгоритмов нет. Этап 11 и 7.5c не начаты.
Policy DRY_RUN, manual authorized control, RF/IF untrusted остаются обязательными.
Ниже сохранена история предыдущих этапов.

# Stage 9 — единый демонстрационный сценарий

Ветка feature/system-integration-demo от d3cd219e39c719c6a53db057c58635f2b0410a8d.
Объединены inventory/card/history/security/Policy/manual crypto UX в Flask.
Новые bounded read-only snapshots и receiver heartbeat; прежние mutating control
и Mongo history APIs переиспользованы. New/resume lab scripts создают отдельный
lcm-stage9-demo-* project без reset прежних keys/nonce/SQL state.

Проверки: STAGE9_RESULTS.md, browser desktop/mobile artifacts, реальные HTTP→HMAC→
Device Agent→AEAD telemetry→PG/Mongo receipts, controlled service failures и
поведенческие mutations. Полная регрессия 715 passed, 0 skipped; baseline 703
сохранён, новые tests не заменяют проверку scientific IDS качества.

Policy DRY_RUN, RF/IF RESEARCH/DEMO, trusted_detector=false. Этапы 10/7.5c не начаты.
Ниже сохранены исторические итоги предыдущих этапов.

# Этап 8-fix — MQTT input hardening

Ветка `feature/adaptive-crypto-control-fix`, baseline `67eb3bcff937c2b0975b18444680e98af84e76fd`.
Исправлен exact-type guard outer profile; добавлены malformed telemetry/AAD,
подписанные control/ACK negatives, PG/SQLite invariants и real TLS poison probe.
Проверены Ascon↔AES и recovery существующего протокола; новый recovery protocol
не создавался. Фактические результаты/команды/exit codes — STAGE8_FIX_RESULTS.md.

Этапы 9 и 7.5c не начаты. Policy DRY_RUN; RF/IF RESEARCH/DEMO,
trusted_detector=false. Исторические результаты ниже сохранены как история.

# Этап 8 — real manual crypto control проверен

Ветка feature/adaptive-crypto-control, исходный f6f3c23. Реальные software IoT
Ascon↔AES-GCM, authenticated PREPARE/ACTIVATE, verified telemetry evidence.
Policy Worker — DRY_RUN, trusted_detector=false; никакого auto ML control.

| Компонент | Статус | Фактическая проверка |
|---|---|---|
| AES/Ascon | проверено KAT/интеграцией | Два AEAD,99crypto checks, реальные пакеты |
| Live control | реализовано / проверено | Manual admin HTTP + HMAC + точные TLS ACL |
| Device Agent | проверено software |3devices, durable SQLite, restart/fail-closed |
| Nonce/replay | проверено | PG boot ranges, independent command ledger, mutation reuse rejected |
| PG state/evidence | проверено |0007/0008 additive,42tables, rollback/retention preservation |
| Actual switching | проверено | Ascon→AES→Ascon, real PG/Mongo references,2controllers |
| Recovery | проверено с ограничениями |9real cases + late real ACK; PREPARE-only expiry/manual repair ограничения |
| Flask/Socket.IO | проверено | RBAC/CSRF/redirects, actual HTTP/socket, viewer denied control |
| Regression | проверено |401passed,0skipped, exit0;337previous+64new |
| Mutations | проверено |9/9 behavioral defects detected in temporary copies |
| Performance | измерено |18micro cases,6static windows,4switches; software/x86 only |
| Scientific ML/physical ARM | не проверено | Новых моделей/доверенности/ARM claims нет |

STAGE8_RESULTS.md описывает команды, факты, ограничения и raw reports.
Старые datasets/models/plans сохраняются; push/merge/main не выполнялись.

## Исторический итог 7.5b-fix

# Состояние разработки — 7.5b-fix

Ветка feature/mqtt-tls-ground-truth-hardening от 3282557. Корректирующая инженерная
часть завершена; обучение 7.5c заблокировано качеством/поддержкой данных.

| Компонент | Статус | Факт |
|---|---|---|
| Test/source audit | выполнено | Реальный old-validator false acceptance, классификация mocks/fixtures/real services |
| Independent reconciliation | проверено | Raw PCAP +separate oracle, logical tamper при coherent hashes отвергается |
| Label semantics | исправлено v2.2 | Connection/window, не malicious packet; unknown не normal |
| Scenario corroboration | проверено частично | Broker/PG/digest, real ACL/auth/replay/rate/pattern; tamper не подтверждён |
| Archived7.5b dataset | сохранён / не train-ready |59 captures, новая версия 46395 unknown;0 known groups |
| New real small dataset | проверено инженерно |9 captures,2269 rows:1509 normal/190 controlled/570 unknown |
| New split gates | отказ ожидаемый |Archive no independent labels; live9/5 groups, новые plans отсутствуют |
| Old split audit | выполнено |Original indices сохранены; coverage gaps, shared seeds7/9/2 |
| Mutations | проверено |8behavioral mutants killed, initial coverage gap документирован |
| Full regression | проверено |337 passed:301 прежний+36 новых, реальные свои PG/Mongo |
| Actual TLS/fault/web/ML/Policy | проверено |Own projects only, no applied crypto, role/CSRF/TLS/ACL сохранены |
| Scientific label/model accuracy | не проверено |Нет внешнего gold standard/реальной новой RF/IF оценки |

Архив/модели/старый frozen plan не изменены, main/push/merge не выполнялись.
Текущий итог: [RESEARCH_75B_FIX_RESULTS.md](RESEARCH_75B_FIX_RESULTS.md).
Проверки и machine reports: docs/reports/stage75b-fix-*.

## Историческое состояние 7.5b (готовность labels пересмотрена выше)

# Состояние разработки — этап 7.5b

Ветка `feature/mqtt-tls-dataset-collection`, исходный `d4dc3aa`.
Инженерный контур и ограниченный лабораторный набор реализованы; доверенное
обнаружение реальных атак не подтверждено. Реальные новые RF/IF не обучались,
final holdout не оценивался, trusted_detector=false/Policy DRY_RUN сохранены.

| Компонент | Статус | Фактическое доказательство / ограничение |
|---|---|---|
| Separate Compose lab | проверено интеграцией | Internal network, свои PG/Mongo/Mosquitto/Policy/volumes, без host ports |
| Virtual devices | проверено интеграцией |24отдельных credentials/keys, до20одновременно, TLS/Ascon/v2/counters |
| Bounded scenarios | проверено интеграцией |6normal+6controlled violations; ограничения CPU/RAM/time/rate/disk/load |
| Passive collector | проверено интеграцией | publisher→broker eth0, tcpdump/tshark; kernel drops0; no TLS decryption |
| Ground truth | частично подтверждено | socket tuple+SYN+clock+outcome; unknown сохранены, абсолютная точность не измерена |
| Dataset / curation | проверено |70основных captures,10явных exclusions,1quarantine;59valid,46395packets |
| Strict split | проверено |6645/2082/2035rows после purge;≥5групп каждого класса/часть, без leakage |
| Frozen old models/reports | проверено хешами |13файлов неизменны; source crypto/ML/Policy/Outbox unchanged |
| Full regression | проверено |301pytest + real TLS/ACL/storage/ML/Policy/web/Chromium |
| Collector fault isolation | проверено | stopped clients2.185s,52сообщения дошли вMongo, applied0 |
| External dataset additions | только аудит |MQTT_UAD/MQTTEEB-Dv2/IoT-SFCv2: лицензии/гранулярность/feature gaps; без merge |
| New RF/IF quality | не проверено |Нет новых real-data models/metrics;7.5c только по команде |
| Host/ARM/real attack generalization | не проверено |Один Docker host, лабораторные нарушения, возможные shortcuts |
| Disk hard quota / peak tshark RSS | не проверено |Есть watchdog budget/CPU/RAM quotas, нет filesystem hard quota |

Итог, команды и ограничения: [RESEARCH_75B_RESULTS.md](RESEARCH_75B_RESULTS.md).
Полный machine report: [stage75b-collection.json](reports/stage75b-collection.json).
Сырые данные в private `.local-runtime/stand75b/`, PCAP/CSV/keys не вGit/images.

## Историческое состояние этапа 7.5

Ветка feature/ml-research-improvement отc9250d8. Инженерная часть реализована,
научная оценка улучшенного RF/IF **заблокирована недостатком пригодных independent
captures и неполученными внешними архивами**. Новых real-data fitted artifacts нет.
ML/Policy остаются RESEARCH/DEMO, trusted_detector=false, policy DRY_RUN.

| Компонент | Статус | Факт / ограничение |
|---|---|---|
| Frozen stage6 baseline | проверено тестами/хешами | 13 files unchanged: notebook,2 reports,5 моделей+manifests |
| RF diagnosis | выполнено | normal validation scores1.0; purge694→9,1 group/1 vector; threshold>1 |
| Historical per-attack IF errors | выполнено, ограниченный baseline | ICMP/UDP recall0; TCP.6271; MITM.9822 (не новый benchmark) |
| MQTTset metadata/license | проверено | v5, CC BY-NC-SA4.0, limited public files без аккаунта |
| Raw import | проверено на реальных данных |14501 packet rows,1 attack capture,0 normal; plan отвергнут |
| Reduced audit | выполнено |330926 rows/209499 identical reduced rows, provenance удалена |
| MQTT-IoT-IDS2020 | частично проверено | Public page200/CC BY4.0, login/subscription download UI, archives не получены |
| Feature contract/extractor | проверено unit tests | tcp-packet-passive-v1,5 TCP fields, no zero-fill missing columns |
| RF/IF experimental workflow | проверено unit tests | capture split, train-only transforms/weights, normal-only IF, frozen test |
| Новые реальные модели/quality | не выполнено | strict gates не разрешают обучать на неподходящем split |
| External source benchmark | не выполнено | Нет файлов/совместимого prepared source/внутреннего frozen model selection |
| Baseline inference cost | измерено ограниченно | Frozen validation1227, x86_64,6ms single/35k rows/s batch, не production guarantee |
| Runtime collector / TLS generalization | отсутствует / не проверено | Только технический проект, пассивно видимые поля ещё не runtime feed |
| Telemetry IF | сохранён DEMO | Нет новых реальных размеченных физических данных |
| Existing system regressions | проверено |267 pytest + real recovery/TLS/ACL/ML/Policy/HTTP/Chromium |
| Crypto/Policy/FastAPI/Magma/CRISP | не изменялись | Ascon/TLS/v2/replay/roles/DRY_RUN сохранены |

## Git и результаты

ac6d4d7 — исходная RF diagnosis и source provenance.
8b4795b — strict packet import, frozen RF/IF experiment pipeline,12 unit tests.
504ac6f — capture support failures, historical attack errors и baseline inference costs.
02c67b1 —267 tests и реальные runtime/security/recovery регрессии.
Дальнейшие verification/docs commits — git log c9250d8..HEAD; финальный hash в отчёте.

Последний полный прогон267 passed in27.24s, без skips/warnings, прежние255 включены.
Отдельно реальные3 устройства/TLS/ACL/replay/Outbox crash/Mongo/PG outage/ML recovery,
2 Policy Worker/restart/readiness, Flask roles/CSRF/Socket.IO и Chromium12 payloads.
Версии/команды/config/hashes/counts — reports/STAGE75.md и stage75-research-results.json.
Новые weighted/tuned models только предусмотрены матрицей9 specs/14 fits; эффекты
на реальных данных не оценены. Synthetic unit results не являются scientific metrics.

Изолированный lcm-stage75 остановлен без удаления volumes; private data/models
сохранены. Нет push/merge/rebase/main изменений. Следующий основной этап не начинается.
Текущие источники/готовность/что предоставить — ML_DATASET_COMPARISON.md,
ML_RESEARCH_7_5.md и ML_GENERALIZATION.md. Далее исторический этап7.

---

# Состояние разработки — этап 7

Инженерные требования этапа7 выполнены в feature/adaptive-policy-engine от6aedf52.
Policy Engine работает в DRY_RUN, отдельный simulator — в SIMULATION. Реальное
переключение криптографии не реализовано и не заявляется. Main/push/merge не менялись.

| Компонент | Статус | Фактическая граница |
|---|---|---|
| Signal Adapter / Policy Signal v1 | проверено тестами | Schema/source allowlist, provenance, typed ML scale/status/version |
| Protocol journal | проверено тестами | AEAD-проверенные device bindings; rejected без device, bounded100000/overflow |
| Risk FSM | проверено тестами | NORMAL/WATCH/ALERT/CRITICAL/UNKNOWN, guard и позитивное восстановление |
| Hysteresis/cooldown/rate limit | проверено тестами | Отдельные escalation/recovery thresholds, continuous history, no empty-queue recovery |
| Crypto registry | проверено тестами | Только Ascon-AEAD128, capability/minimum guards, unsupported profiles отклоняются |
| PG states/decisions/audit | проверено тестами | 0005+0006, всего34 таблицы, atomicity/dedupe/concurrency/version guards |
| Control contract/counters | проверено тестами | Independent epoch/sequence, TTL/identity, proposal persistence; без отправки |
| ACK simulator | проверено тестами | Explicit simulation authorization/replay/expiry/snapshot; не криптографическая auth |
| Policy Worker | проверено тестами | Optional PG-only, DRY_RUN, bounded polls, graceful stop, actual PG outage/readiness/restart |
| Flask /policy и API | проверено тестами | Read roles, admin+CSRF activation/audit, textContent, no fake applied state |
| Simulation experiment | проверено тестами | 13 synthetic scenarios ×4 variants, deterministic traces/configs, applied_changes=0 |
| Runtime MQTT/Mongo/Outbox/ML | проверено тестами | Старые regression/recovery/security проверки сохранены и повторены |
| Live control/device ACK/applied state | отсутствует | Требует device handler, control auth/key separation/ACL и reconciliation |
| Trusted online critical source | отсутствует | security_violation только контролируемые tests/simulation, broker logs не подключены |
| Trusted ML attack detector | не проверено | DEMO/RESEARCH, trusted_detector=false; scientific limits этапа6 сохранены |
| Большие нагрузки / ARM64 / HA | не проверено | Малый smoke не доказывает1000msg/s/10000 устройств |
| «Магма»/CRISP/FastAPI | отсутствует | Не разрабатывались на этапе7 |

## Git блоки

1ea9fcc — contracts/FSM/capabilities/control simulator.
c184f6b — PG journal/migrations/state/audit/worker/independent counters.
b29621c — deterministic policy experiments.
370883a — authorized policy dashboard/admin/CSRF/Chromium checks.
eb403e2 — UNKNOWN/identity/rate/provenance/recovery refinements.
030abe5 — full regressions/security/recovery protocols.
Финальный documentation hash указан итоговым отчётом; не помещается внутрь себя.

## Проверки

Последний полный pytest:255 passed in24.45s, без skips/warnings. Прежние233 входят.
Дополнительно real two-worker/restart/PG outage/readiness; policy off → telemetry
continues; реальные replay трёх устройств/forged AAD; Mongo/PG outage/relay crash;
ML missing model/reload/Mongo outage; TLS/password/CA/ACL; HTTP/Socket.IO/CSRF;
Chromium12 injection payload checks. Ruff/compileall/Node и known-secret/Git/три
образа прошли. Промежуточные неуспехи сохранены в reports/stage7-*.txt.

Нормативная криптопроверка, реальные control commands/ACK, качество ML и большой
benchmark не подтверждались. Только synthetic policy comparison: oscillation17→1
risk transitions с hysteresis; replay reaction1→2 модельные секунды. Никаких
фактических algorithm switches. Метрики/условия — POLICY_EVALUATION.md.

## Операционные ограничения

Source finite journal/explicit retention и coverage gaps; audit/tombstones capacity
plan; shared PG role/DB TLS/HA остаются. Unscored/stale ML не считается нормой.
Active policy change сохраняет guard; Applied Configuration всегда NULL.
Изолированный lcm-stage7 остановлен без удаления volumes; источники, ключи,
счётчики и прежняя модель сохранены. Протоколы/матрица: reports/STAGE7.md. Полный список файлов: reports/stage7-files.txt.

Ниже сохранена историческая база этапа6; будущие этапы автоматически не начинаются.

---

# Состояние разработки — этапы 0–6

2026-11-09. Инженерная часть этапа6 реализована в feature/ml-inference-pipeline
от cfda660 (feature/mongodb-telemetry-storage). Source notebook неизменён.
Push/merge/rebase/main не выполнялись. Следующий этап автоматически не начинается.
Подробные протоколы: reports/STAGE6.md; прежний статус — git show cfda660:docs/DEVELOPMENT_STATUS.md.

## Сохранённые этапы и блоки

| Этап | Git / результат |
|---|---|
| 0 | safe baseline908dd56+c352d81 в main |
| 1 | inventory76ca884 |
| 2 | reproducible PostgreSQL runtime fca2153 |
| 3 | Compose/Mosquitto5be5444 |
| 4 | security-hardening d9a000f,177 pytest |
| 5 | dual database/outbox/worker cfda660,210 pytest |
| 6 аудит | 6705332 —13 ячеек, dataset/feature/методика; исходный notebook сохранён |
| 6 offline ML | fa5f9be —typed schemas, train-only pipelines/splits/metrics, causal telemetry, hashed artifact export |
| 6 async/PG | e54c169 —bounded feed, model registry, leases/events, optional ML image/worker |
| 6 web | c5874ee —authorized events/status/UI, раздельные источники |
| 6 fixes | a577074 —fenced completion race, causal/schema bounds |
| 6 verification | 462f2b7 —recovery/security regression, real-data aggregates |

Дальнейшие fix/test/docs commits — git log --oneline cfda660..HEAD. Final hash
указан итоговым отчётом, а не помещается внутрь своего коммита.

## Текущее состояние

| Компонент | Статус | Фактическое доказательство / граница |
|---|---|---|
| MQTT publisher/broker/ingestion | проверено тестами | TLS/ACL/AEADv2/replay сохранены, core callback не запускает ML |
| PG/Mongo/Outbox | проверено тестами | Предыдущие recovery/concurrency/replay и реальные container outages/crash повторены |
| Legacy schema / Alembic | проверено тестами | 23 таблицы,0004ML добавлена; stage5 rows/outbox/replay сохраняются |
| Network IDS RF binary/multiclass/IF | проверено тестами | Engineering pipeline и limited real Edge experiment; не production attack detector |
| Real Edge source | существует | 2219201 строка,63 поля,15 Attack_type, hash/labels/types audit; license unverified |
| Independent network validation | не проверено | Host-pair proxy, не physical device/session holdout; chronology неполна; val normal9 |
| RF качество | частично реализовано | Binary macroF1.3328/recall0, multiclass fixed15 macroF1.1373; модель недоверенная |
| IF Network качество | частично реализовано | Binary macroF1.7296/FPR0 на ограниченном test2005; не generalization guarantee |
| Network live collector | отсутствует | MQTT sensors не имеют DNN network feature vector |
| Telemetry statistical / IF | проверено тестами | Обе обучены на320 synthetic records4 devices, split180/60/60 после warmup |
| Telemetry real quality | не проверено | Нет representative physical baseline/independent labels; псевдоточные метрики не вычисляются |
| Model export/load | проверено тестами | Pipeline+manifest/hash, owner/mode/path/schema/version checks, tamper rejection |
| Optional inference worker | проверено тестами | Mongo→bounded features→PGevents, missing model/dedupe/restart/Mongo recovery |
| ML queue/checkpoint | частично реализовано | Durable bounded markers100000 + gaps, no measured_at-only cursor; pre-cutover/full-history coverage не гарантирована |
| ML results / Policy signal | проверено тестами | Unique device/epoch/seq/model/version, finite score, explicit mode/scales; не выбирает crypto |
| Flask/Socket.IO/security | проверено тестами | Прежние auth/roles/CSRF/TLS/ACL + real HTTP ML pages/events/status |
| Additional datasets | существует | Подбор MQTTset/MQTT-IoT-IDS2020/MQTT_UAD/CICIoT2023 в ML_DATASETS.md; не скачаны/не обучены |
| Большие нагрузки / ARM64 | не проверено | CPU/memory/window limits есть,1000msg/s и10000 устройств не измерялись |
| Policy Engine / FastAPI / «Магма» / CRISP | отсутствует | В этапе6 не разрабатывались |

## Результаты и ограничения

Полный текущий pytest:233 passed, без skips/warnings; прежние210 включены.
Отдельно real Docker ML missing-model/restart/dedupe/Mongo retry/recovery,3 устройства;
старые PG/Mongo outage/relay crash/replay/TLS/ACL/HTTP/Socket.IO проверки.
Актуальный финальный прогон/статические/security/Chromium результаты — reports/STAGE6.md.
Промежуточные errors сохранены; исходный CSV auditor C-engine SIGSEGV исправлен
raw-string Python-engine чтением; полный аудит завершён успешно,0 label conflicts.

Реальные Network модели обучены на11851-row subset, не на всём DNN: после purge
train5630/val1227/test2005, IF fit1961normal. Высокое качество RF не заявляется.
Локально подтверждены label proxies0/0.0; данные и weights остаются приватными.
Scientific metrics, integration success и DEMO telemetry не смешиваются.

ML off по умолчанию, research opt-in явный. Feed finite и retained даже после
score; нужны capacity/prune, overflow сообщает gap без остановки telemetry.
Retrospective coverage, source-clock correctness, shared PG role, production HA/TLS,
real anomaly labels и независимая device/session оценка остаются ограничениями.

Финальные уточнения: canonical fingerprint purge проверен без пересечений;
последовательность device/epoch/sequence и монотонность обеих дат определяют causal
окно. Исправлена гонка expired claim vs completion повторным event row lock.
Полный233-test прогон прошёл; модельные артефакты не менялись ради улучшения test.

Изолированный lcm-stage6 остановлен после проверок (stage6-shutdown.txt).
Команда down выполнена без --volumes: БД, счётчики, model volume и приватные
материалы сохранены. Предыдущие контуры/volumes не удалялись.

## Stage11: Kuznyechik-MGM software integration

Реальная реализация и сквозные Ascon→Kuznyechik→AES→Kuznyechik→Ascon переходы проверены через MQTT/TLS, настоящий Device Agent, HTTP admin, PG receipts и Mongo. Доступ ограничен явным isolated lab authorization; ARM/production/сертификация не заявляются. Policy DRY_RUN; RF/IF RESEARCH/DEMO, trusted_detector=false. Точные результаты, команды/exit codes и ограничения: [STAGE11_RESULTS](STAGE11_RESULTS.md). Этап12/Magma/7.5c не запускались.

## Этап 12 — инженерная и сравнительная проверка

Завершены аудит provider/Python кандидатов, bounded worker, KAT/negative/concurrency/crash/recovery/mutation проверки, независимые benchmark repeats и реальные Stage12 MQTT/HTTP/Chromium сценарии. Baseline868 → итог882 passed/0 skipped;25 поведенческих мутаций обнаружены. Новый изолированный cohort3:27/27 telemetry-confirmed transitions, PG/Mongo7689/7689 после drain. Не является новым capacity/IDS/constant-time доказательством.

Magma исследована, live gate отрицательный; непрерывная активация запрещена, rekey не реализован. Три прежних AEAD сохранены, Kuznyechik lab-only, Policy DRY_RUN, trusted_detector=false. Стенд остановлен с сохранением volumes/keys. Подробные числа, команды, SHA и ограничения: [STAGE12_RESULTS](STAGE12_RESULTS.md). Этап13 не начат.

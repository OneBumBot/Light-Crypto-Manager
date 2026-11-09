# Этап 7.5 — исследование в feature/ml-research-improvement

Исходная база c9250d8 сохранена. Диагностика frozen RF: все9 normal validation
имеют risk1.0, поэтому FPR constraint выбирает threshold>1. Новый packet extractor
и offline RF/IF pipeline реализованы отдельно; network-core-v1 не переписан.
12 новых unit-тестов проходят, промежуточный полный контейнерный прогон265 passed.
MQTTset v5 metadata license CC BY-NC-SA4.0 подтверждена публичным API; реальные
raw14501 и reduced330926 строк проверены. Reduced утратил capture/session metadata,
normal raw capture только один: строгий benchmark и обучение новых реальных
моделей заблокированы недостатком независимых normal captures. IEEE DataPort
недоступен; внешний benchmark не выполнен. Научное улучшение RF/IF не заявляется.
Итоговые regression/документация ещё выполняются. Ниже исторический этап7.

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

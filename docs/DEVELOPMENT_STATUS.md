# Этап 7 — разработка в feature/adaptive-policy-engine

Исходная база 6aedf52 сохранена. Реализованы Policy Signal v1, DRY_RUN FSM,
конфигурация hysteresis/cooldown, capability registry и формальный control contract.
0005_policy/0006_policy_control добавляют 11 таблиц (всего34), не меняя старые данные.
Состояние, аудит и дедупликация транзакционны; worker опционален и не посылает MQTT.
Ascon-AEAD128 — единственный реальный профиль; Applied Configuration не подтверждена.

Проверки блоков:12 pure unit и19 policy engine/storage tests на настоящем PG.
Промежуточный полный прогон252 passed; real two-worker/restart/PG outage прошёл.
Текущие допроверки веба, ML/Outbox regression и итоговая документация ещё продолжаются.
Этап7 пока не объявлен завершённым. Протоколы: reports/stage7-*.txt.

Далее сохранён итог этапа6 как историческая база.

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

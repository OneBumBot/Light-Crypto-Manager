# Дополнение Stage 9: единый локальный стенд

Используются compose.yaml + compose.control.yaml + compose.stage9.yaml;
project строго lcm-stage9-demo-*. Prepare создаёт новые credentials и 3 устройства,
run_stage9_demo start --build применяет migrations до 0009, запускает TLS/PG/Mongo/
receiver/relay/web/Policy DRY_RUN/Control MANUAL_AUTHORIZED_CONTROL и agents.
ML выключен явно; web читает PG snapshots вместо собственного MQTT buffer.
Loopback ports выделяются Docker, URL выводится после реальной telemetry readiness.

Безопасные new/resume/stop commands, private account provisioning через stdin,
CPU/RAM/log limits и missing-volume guard: STAGE9_DEMO_RUNBOOK.md.
Stop сохраняет volumes. Исторические Compose инструкции ниже относятся к прошлым
профилям и не заменяют Stage 9 runbook.

# Этап 7: optional Policy Worker (DRY_RUN)

Используйте существующие env/project/volumes/ключи/счётчики. Примените additive
миграции0005/0006 до запуска обновлённого ingestion; volumes не удалять:

```bash
docker compose --env-file .env.compose build receiver
docker compose --env-file .env.compose run --rm init-db
docker compose --env-file .env.compose --profile demo --profile web up -d --wait
# Политика по умолчанию выключена; отдельный явный запуск:
docker compose --env-file .env.compose --profile policy up -d --wait policy-worker
```

POLICY_MODE всегда DRY_RUN; другие режимы worker отклоняет. POLICY_BATCH_SIZE32,
диапазон1..128, CPU1/memory256MiB. Контейнер не получает MQTT/Mongo ключи и не
загружает ML. Readiness обновляется только после успешной PG обработки, снимается
при ошибках; heartbeat и staleness видны /policy и /api/policy.

Worker создаёт default-v1 только при отсутствии активной политики. Admin через
/policy может создать immutable JSON версию/активировать её с CSRF и audit.
Viewer/operator читают данные при существующем праве sensor_data; менять политику
не могут. /api/policy/metrics только admin. Настройка источников ML не делает их
доверенными: без scored ML ожидаем UNKNOWN, основной MQTT контур работает.

## Retention и ограничения

Source journal capacity100000. При overflow сохраняется primary telemetry, но
теряются новые policy observations; следите за retained/overflow/queue_pending.
Автоматической очистки нет. Явная bounded операция при остановленных worker:

```bash
docker compose --env-file .env.compose stop policy-worker
docker compose --env-file .env.compose run --rm --no-deps policy-worker python -m src.policy.worker --prune-days 30
```

До1000 старых decisions и обработанных source observations за вызов; proposals
сохраняются, replay и ML не удаляются. Signal identity tombstones остаются, raw
payload при явной audit retention теряется. Сделайте отдельный архив оснований
до очистки. Историческая coverage новой версии не гарантирована. Capacity при
необходимости меняется явной проверенной admin DB операцией (положительное значение),
не через непривилегированный HTTP endpoint. Полные ограничения в KNOWN_ISSUES.md.

## Воспроизводимые проверки

Разработка использует только отдельный lcm-stage7 project с новыми volumes и
0700/0600 материалами. Существующие контуры не используются для fault tests.
После подготовки приватного stage7.env с тремя дополнительными device identities:

```bash
docker compose --env-file .local-runtime/stage7.env run --rm --no-deps tests
python3 scripts/check_policy_system.py --env-file .local-runtime/stage7.env
python3 scripts/check_dual_database.py --env-file .local-runtime/stage7.env
python3 scripts/check_ml_system.py --env-file .local-runtime/stage7.env
```

ML regression требует явно заданного private model directory и research opt-in
в isolated env. Используется прежний stage6 DEMO artifact, без нового обучения.
Повтор с установленным model volume: --reuse-installed-model. Протоколы с
командами/кодами — reports/stage7-*.txt. Ниже сохранено руководство основной системы.

---

# Этап 6: optional ML поверх защищённого двухбазового контура

Базовый MQTT/PG/Mongo запуск ниже сохранён. Актуально23 PG таблицы (Alembic0004).
ML выключен по умолчанию: профильml отдельно, ML_ALLOW_RESEARCH=0. Default runtime
image не содержит sklearn/weights; отдельные ml/tests targets содержат минимальные
ML библиотеки без датасетов/готовых моделей. Network IDS работает только offline.

## Переход с этапа 5 без пропуска delivery markers

Используйте прежние env/project, сохраните volumes/keys/counters. До применения
0004 остановите **старый relay**, затем примените миграцию и запустите новую версию:

```bash
docker compose --env-file .env.compose stop outbox-relay
docker compose --env-file .env.compose build receiver
docker compose --env-file .env.compose run --rm init-db
docker compose --env-file .env.compose up -d --wait receiver outbox-relay
```

Receiver может накапливать outbox до возобновления relay. Старые таблицы и replay
сохраняются. Retained delivered outbox backfilled до100000; уже очищенная история
Mongo до cutover не гарантированно покрыта. Новые ML markers bounded; overflow
виден в ml_feed_state, не блокирует primary delivery. Без явной retention markers
занимают capacity даже после оценки: планируйте prune/capacity, см. ML_INFERENCE.md.
Рабочие volumes этапа5 при разработке/сбоях не использовались; тесты в lcm-stage6.

## Explicit DEMO artifact для инженерной проверки

Не используйте synthetic генерацию вместо недоступных реальных attack данных.
Следующие команды только для воспроизводимого smoke (не trusted detector):

```bash
.venv/bin/python -m src.classifier.ml.demo --synthetic-demo --device raspb1 --device alpha --device beta --device gamma --output .local-runtime/ml-demo/train.csv --config-output .local-runtime/ml-demo/train.json
.venv/bin/python -m src.classifier.ml.train train --data .local-runtime/ml-demo/train.csv --config .local-runtime/ml-demo/train.json --models-dir .local-runtime/ml-models --report .local-runtime/ml-demo/report.json
```

Модель может оценивать только обученные device baselines; для вашего набора
устройств/настоящих данных используйте собственную проверенную выборку/версии.
Не устанавливайте незафиксированные internet pickle/joblib. Все model/data пути
приватные, loader требует0700/0600 и exact library versions.

В приватном .env.compose задайте (последняя строка — осознанный research opt-in):

```dotenv
ML_MODELS_DIR=.local-runtime/ml-models
ML_MODEL_ID=telemetry-statistical
ML_MODEL_VERSION=1.0.0
ML_ALLOW_RESEARCH=1
ML_BATCH_SIZE=16
```

Затем:

```bash
docker compose --env-file .env.compose build ml-worker
docker compose --env-file .env.compose run --rm --no-deps ml-model-init
docker compose --env-file .env.compose --profile ml up -d ml-worker
```

ml-model-init — отдельный trusted root tool, не startup dependency: проверяет
manifest/hash без root unpickle, копирует выбранную immutable версию в volume
ml-models с UID10001,0700/0600. Worker монтирует его read-only и имеет только Mongo
history read credential; MQTT credentials/ключей у него нет. Missing/invalid model
→unavailable, default no opt-in→disabled. При остановке ML telemetry работает.

UI `/ml` и API `/api/ml/events`, `/api/ml/status` требуют login/sensor_data permission.
Model heartbeat, per-model score semantics, feed gaps, counts/prepare/infer/ACK lag
доступны там. Модель не выбирает crypto profile, API только читает PG результаты.
Подробнее: ML_TRAINING.md, ML_FEATURE_CONTRACT.md, ML_INFERENCE.md.

## Изолированные проверки этапа 6

Создайте отдельный project **lcm-stage6*** и credentials как в базовом руководстве,
с `--extra-device alpha --extra-device beta --extra-device gamma`. Ни чужие volumes,
ни ключи старого проекта не переиспользуются для отказов. Example env для фактически
проверенного project — приватный .local-runtime/stage6.env (в Git его нет).

```bash
docker compose --env-file .local-runtime/stage6.env build tests receiver ml-worker
docker compose --env-file .local-runtime/stage6.env run --rm tests
python3 scripts/check_ml_system.py --env-file .local-runtime/stage6.env
```

check_ml_system первый запуск требует **пустого ML model volume**: доказывает,
что missing artifact не останавливает MQTT/Mongo; устанавливает локальный DEMO,
публикует controlled samples3 устройств, проверяет scores/restart/dedupe, затем
Mongo outage/recovery с сохранёнными ML events. Повтор без удаления state volumes:

```bash
python3 scripts/check_ml_system.py --env-file .local-runtime/stage6.env --reuse-installed-model
```

Повтор пропускает только уже проверенную initial missing-model фазу, сохраняет
counter SQLite; не очищает replay/историю. Source probes используют отдельные
credentials/keys/topic ACL. Статистическое качество атак этим smoke не оценивается.

```bash
docker compose --env-file .local-runtime/stage6.env run --rm --no-deps -e WEB_EXPECT_ML=1 --entrypoint python tests -m scripts.live_web_smoke
docker compose --env-file .local-runtime/stage6.env run --rm --no-deps --entrypoint python tests -m scripts.mqtt_security_smoke
docker compose --env-file .local-runtime/stage6.env run --rm --no-deps smoke --expect-demo
python3 scripts/check_dual_database.py --env-file .local-runtime/stage6.env
```

Последняя команда также останавливает PG/Mongo и аварийно завершает одноразовый
relay после Mongo write. Разрешены только изолированные lcm-stage5/lcm-stage6 project
prefixes, но правильный выбор env/volumes всё равно обязан проверить оператор.
Полные очищенные протоколы и матрица — reports/STAGE6.md.

Остановить и сохранить все state/model/security volumes:

```bash
docker compose --env-file .env.compose --profile demo --profile web --profile checks --profile ml --profile ml-tools down
```

`--volumes` не добавляйте. ML не требует изменения протокола, collector,
Policy Engine/commands/ML quality/1000msg/s не считаются подтверждёнными автоматически.

---

## Базовое руководство этапа 5 (с учётом уточнений выше)

# Локальный двухбазовый защищённый контур — этап 5

Python 3.12.16, закреплённые образы PostgreSQL 17, MongoDB 8.0.17, Mosquitto 2;
точные digest — compose.yaml. MongoDB/PostgreSQL не публикуют порты наружу.
MQTT TLS/8883 и локальный Flask HTTP/5000 привязаны к loopback. TLS/ACL этапа 4
сохранены. Это dev/research deployment, не production HA.

## Новая установка

Требуются Docker/Compose, Python3, openssl. Проверены Engine29.9.2, Compose5.6.1;
classic builder работает без buildx. Команды из корня:

```bash
mkdir -m 700 -p .local-runtime
python3 scripts/prepare_security.py --directory .local-runtime/security
python3 scripts/prepare_storage.py --directory .local-runtime/mongo-security
python3 scripts/prepare_compose.py
docker compose --env-file .env.compose config --quiet
docker compose --env-file .env.compose --profile demo --profile web up --build -d --wait --wait-timeout 150
```

Генераторы отказываются перезаписывать материалы. Каталоги0700, файлы0600.
Не печатайте `compose config` без --quiet: он разворачивает PG/session secrets.
MQTT/security credentials устанавливает security-init; Mongo credentials —
storage-init. CA private key остаётся на хосте. Client/runtime UID10001;
Mosquitto UID1883, Mongo credentials UID999. Секретов в images нет.

| Сервис | Назначение |
|---|---|
| postgres | Управляющая БД, replay/outbox/metrics/Alembic, постоянный volume |
| mongo | Authenticated ordinary collection measurements, persistent volume, authenticated healthcheck |
| init-db | Alembic upgrade head под advisory lock; завершение обязательно для ingestion/web/relay |
| broker | Только TLS/password/точные per-user topic ACL; readiness через monitor/options file |
| receiver | AEAD/валидация + PG transaction, QoS1 manual ACK, readiness после SUBACK |
| outbox-relay | Короткая PG lease → Mongo insert/сравнение duplicate → PG acknowledge |
| demo-setup / publisher | opt-in demo, два прежних fixture устройства, publisher raspb1 |
| web | Существующие Flask/Socket.IO/live; read-only Mongo history и admin metrics |
| smoke / tests | opt-in checks, отдельные тестовые права, реальные DB тесты |

Mongo роли: relay только insert/find одной collection, history только find;
ни delete, ни index/schema admin. Root только init/администрирование/healthcheck,
не монтируется web/relay. Серверный validator и unique/history indexes создаются
первым init. При существующем Mongo volume init scripts повторно не выполняются;
изменения схемы/ротация требуют явной admin процедуры, а не удаления volume.

## Переход с этапа 4

Сохраните прежние MQTT materials, publisher-state, replay-state и PG volume.
Не запускайте генератор поверх старых файлов и не меняйте COMPOSE_PROJECT_NAME,
если требуется использовать прежние данные. Создайте только новые Mongo materials,
добавьте `MONGO_SECURITY_DIR=.local-runtime/mongo-security` в прежний приватный env.
До первого запуска нового receiver остановите publisher/receiver/web, чтобы
телеметрия не поступала до заполнения нового control registry. Для существующего
локального demo (с тем же env/project и прежними security/state volumes):

```bash
docker compose --env-file .env.compose --profile demo --profile web stop publisher receiver web
docker compose --env-file .env.compose build receiver
docker compose --env-file .env.compose up -d --wait postgres mongo broker
docker compose --env-file .env.compose run --rm init-db
docker compose --env-file .env.compose run --rm --no-deps --entrypoint python receiver -m scripts.provision_registry
docker compose --env-file .env.compose --profile demo --profile web up -d --wait --wait-timeout 150
```

При конфликте provisioning оставьте producers остановленными до ручного разбора;
реальные custom конфигурации не перезаписываются ради demo. Для собственного
набора сервисов выбирайте свои профили без demo fixtures. `init-db` применяет Alembic:

1. 0001 валидирует все существующие legacy columns/types/nullability/PK/unique.
2. Создаёт отсутствующие таблицы, не меняя уже существующие/их данные.
3. 0002 добавляет telemetry_outbox/ingestion_metrics и индексы/constraints.
4. 0003 создаёт несекретный telemetry_devices; заполните его явным provisioning
   (demo-setup заполняет два demo устройства, остальные — provision_registry).

Sensor_Data и replay-state сохраняются. Пустая БД проходит тот же upgrade.
Несовместимая схема вызывает отказ с именем таблицы; не обходите его blind stamp,
не удаляйте БД. Rollback миграций намеренно не удаляет таблицы: нужен разбор и
отдельная проверенная миграция. Перед реальным upgrade сделайте свой backup.
Тесты проверяют legacy transition на изолированной схеме, volumes этапа4 не менялись.

## Несколько устройств

Новый независимый тестовый контур:

```bash
python3 scripts/prepare_security.py --directory .local-runtime/security-stage5-demo --extra-device alpha --extra-device beta --extra-device gamma
python3 scripts/prepare_storage.py --directory .local-runtime/mongo-stage5-demo
python3 scripts/prepare_compose.py --project lcm-stage5-demo --env-file .local-runtime/stage5-demo.env --mqtt-port 0 --web-port 0
```

В приватном stage5-demo.env задайте соответствующие MQTT_SECURITY_DIR и
MONGO_SECURITY_DIR. Дальнейшие команды используют этот --env-file. Новые устройства
получают уникальные ключи и DB IDs из provisioning registry; пользователь MQTT
`device_<device_id>` имеет write только своего exact topic. Consumer ACL генерируется
из реестра, а не анонимного wildcard. security-init обновляет брокерный ACL volume;
после изменения состава реестра перезапустите broker/receiver/web явно, не меняйте
уже действующие key/epoch без процедуры ротации. Дополнительные credentials в
production нужно передавать каждому устройству отдельно (тестовый сервис получает
набор только для проверок). Publisher поддерживает DEVICE_ID, MQTT_USERNAME,
MQTT_PASSWORD_FILE, DEVICE_REGISTRY_FILE и собственный PUBLISHER_STATE_FILE.

После запуска demo/checks PG provisioning остальных устройств выполняется явно:

```bash
docker compose --env-file .local-runtime/stage5-demo.env run --rm --no-deps -e DEVICE_REGISTRY_FILE=/run/lcm/registry.json --entrypoint python tests -m scripts.provision_registry
```

Скрипт идемпотентен, не перезаписывает конфликтующие конфигурации/теги. Алгоритм1
для локального demo должен быть provisioned demo-setup. Общего ключа нет.
Большой генератор устройств/клиентов не добавлялся; повторяемые --extra-device
готовят небольшой fixture. Формат v2 менять ради будущего генератора не нужно.

## Проверки и отказы

```bash
docker compose --env-file .env.compose build tests
docker compose --env-file .env.compose run --rm tests
docker compose --env-file .env.compose run --rm --no-deps --entrypoint python tests -m scripts.mqtt_security_smoke
docker compose --env-file .env.compose run --rm smoke --expect-demo
docker compose --env-file .env.compose run --rm --no-deps --entrypoint python tests -m scripts.live_web_smoke
```

Отдельная проверка с остановкой MongoDB и аварией процесса (только тестовый
project lcm-stage5*, с тремя extra-device и отдельными volumes):

```bash
python3 scripts/check_dual_database.py --env-file .local-runtime/stage5-demo.env
```

Сценарий запускает два relay, три устройства, проверяет запрет чужого topic,
останавливает Mongo, проверяет сохранённый backlog/попытки, восстанавливает Mongo,
останавливает/восстанавливает PostgreSQL для проверки manual ACK, пересоздаёт receiver/restart relay и повторяет пакет. Затем останавливает publisher
и relay, намеренно завершает одноразовый relay процесс кодом19 после Mongo write
до PG acknowledge, запускает relay и проверяет единственность документов.
Код19 — ожидаемый внутренний fault, итоговый код сценария должен быть0.
Рабочие volumes не используются/не удаляются. Не запускайте на ценных данных:
префикс имени — лишь guard, не замена проверки вами выбора env/project.

Очищенные команды, коды и результаты — reports/stage5-*.txt. Для новых отчётов:

```bash
python3 scripts/run_check.py --report docs/reports/local-check.txt --secrets-dir .local-runtime/security --secrets-dir .local-runtime/mongo-security -- docker compose --env-file .env.compose run --rm tests
```

Включены реальные Mongo insert/conflict/schema/role tests, PG rollback/concurrency/
lease/dead/retention, legacy и empty migration. Предыдущие TLS/ACL/CSRF/socket/XSS
проверки сохранены. Chromium-команда этапа4 остаётся в reports/README.md.

## Метрики / обслуживание

`GET /api/telemetry/metrics` — только admin: входящие/сек за указанное окно (60–120s),
accepted/rejected/replay/delivery_retry/delivery_error/delivered за это окно,
outbox по статусам, возраст старейшего недоставленного, средняя задержка за минуту,
точное количество документов Mongo. Это DB-backed snapshot, не Prometheus;
Mongo count может быть дорогим, ограничен timeout. Ошибка БД даёт общий503.

Настройки: MAX_OUTBOX_PENDING=100000, OUTBOX_MAX_ATTEMPTS=12,
OUTBOX_RETENTION_DAYS=0 (явно включаемая очистка delivered), INGESTION_CLIENT_ID.
Mongo TTL выключен; включение/отключение — TELEMETRY_SCHEMA.md. Dead вручную
requeue после исправления причины — OUTBOX.md. Новые поля env можно добавить в
приватный env; допустимые значения нужно выбирать осознанно.

Остановить, сохранив состояние:

```bash
docker compose --env-file .env.compose --profile demo --profile web --profile checks down
```

Не используйте --volumes с действующими ключами/историей. Потеря sender/replay
состояния требует новой эпохи/ключа. После проверок stage5 volumes также сохраняются.
Raspberry Pi параметры TLS/CA/hostname verification не менялись; нужен SAN реального
DNS/IP и явный LAN binding в deployment. ARM64 и нагрузка до1000 msg/s не проверены.
Mongo/PG HA, Mongo TLS внутри сети, FastAPI, ML, Policy Engine и CRISP не добавлены.

## Этап 8: opt-in manual control, только fresh isolated project

Основной compose не включает control services. Новый compose.control.yaml и
MANUAL_AUTHORIZED_CONTROL подключаются явно; Policy остаётся DRY_RUN.

```bash
uv sync --frozen --inexact --group dev --group publisher --group receiver --group web --group ml-runtime
.venv/bin/python -m scripts.prepare_control --directory .local-runtime/my-stage8 --project lcm-stage8-my-check
export COMPOSE_FILE=compose.yaml:compose.control.yaml
LCM_CONTROL_ENV=.local-runtime/my-stage8/compose.env
docker compose --env-file "$LCM_CONTROL_ENV" build receiver tests
# Mongo нужно включить явно, если запускается список отдельных services:
docker compose --env-file "$LCM_CONTROL_ENV" up -d --wait postgres mongo receiver outbox-relay web
docker compose --env-file "$LCM_CONTROL_ENV" --profile control run --rm --no-deps control-init
docker compose --env-file "$LCM_CONTROL_ENV" run --rm --no-deps --entrypoint python tests -m scripts.control_system_probe setup
docker compose --env-file "$LCM_CONTROL_ENV" --profile control --profile policy up -d --wait --scale control-worker=2 control-worker policy-worker device-alpha device-beta device-gamma
docker compose --env-file "$LCM_CONTROL_ENV" run --rm --no-deps --entrypoint python tests -m scripts.control_system_probe roundtrip
docker compose --env-file "$LCM_CONTROL_ENV" run --rm --no-deps --entrypoint python tests -m scripts.control_security_probe
docker compose --env-file "$LCM_CONTROL_ENV" run --rm --no-deps tests
```

setup использует только этот project, создаёт legacy demo+device bindings и live
capabilities. Control worker health требует PG/config provisioning и MQTT SUBACK,
не только существование process. Roundtrip probe создаёт временного admin с
случайным паролем и обращается к **реальному HTTP**, затем удаляет test account.
Для постоянного UI используйте уже существующую процедуру bootstrap admin;
никаких default passwords не добавлено. Страница /control, POST admin+CSRF.

```bash
# Отдельные immutable outputs. Recovery начинается с effective Ascon alpha;
# после roundtrip это выполнено, после benchmark/другого recovery может быть AES.
python3 scripts/check_control_system.py --env-file "$LCM_CONTROL_ENV" --output /private/new-recovery.json --extended
CONTROL_LATE_ACK_PROBE=1 python3 scripts/check_control_system.py --env-file "$LCM_CONTROL_ENV" --output /private/new-late-ack.json
python3 scripts/benchmark_switching.py --env-file "$LCM_CONTROL_ENV" --output /private/new-benchmark.json
docker compose --env-file "$LCM_CONTROL_ENV" run --rm --no-deps --entrypoint python tests -m scripts.crypto_benchmark --iterations 300
# Остановка сохраняет volumes/keys/counters; не добавлять -v:
docker compose --env-file "$LCM_CONTROL_ENV" --profile '*' down --timeout 15
```

Recovery helpers сами ограничены lcm-stage8-*; target broker/web внутренние.
Control ACK negative probe требует недавний normal completed ACTIVATE ACK;
запускайте сразу после roundtrip, а не после intentionally dropped ACK.
Late-ACK-only probe повторяет неизменённые bytes реального device ledger.
Перед каждым recovery самостоятельно проверяйте начальный profile через status;
возврат AES→Ascon только новой авторизованной командой, не ручным UPDATE state.

Existing Mongo schema с Ascon-only enum обновляется явно (сначала backup/review):
`docker compose --env-file "$LCM_CONTROL_ENV" exec -T mongo mongosh --quiet --file /upgrade_profiles.js`.
Операция аддитивна/idempotent, records/indexes сохраняются. Проверка на собственной
лабораторной БД: scripts/verify_mongo_profile_upgrade.py. Старые рабочие volumes
для этого fault/probe не используются. Существующие legacy publishers Ascon не
получают control capabilities автоматически; переход требует reviewed account/
ACL/key provisioning и остановки второго producer той же identity.

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

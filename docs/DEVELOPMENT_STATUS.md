# Состояние разработки

2026-11-09. Выполнены только этапы0–5. Ветка этапа5:
`feature/mongodb-telemetry-storage`, база `feature/security-hardening`/`d9a000f`.
Push, merge, rebase и изменение main в этапе5 не выполнялись. Рабочие volumes
этапа4 не использовались. Отчёты: [reports/STAGE5.md](reports/STAGE5.md).
Исторический подробный статус0–4 доступен в `git show d9a000f:docs/DEVELOPMENT_STATUS.md`.

## Сохранённые этапы

| Этап | Результат / коммит |
|---|---|
| 0 | Safe baseline908dd56 + permissions c352d81, main |
| 1 | Inventory76ca884, feature/component-inventory |
| 2 | PostgreSQL/runtime fca2153, feature/reproducible-postgres-runtime |
| 3 | Compose/Mosquitto5be5444, feature/local-mqtt-compose |
| 4 | TLS/auth/ACL, MQTTv2/replay/web177 tests; d9a000f и пять предыдущих security commits |
| 5.1 | MongoDB auth/scoped roles/volumes/health:1fff057 |
| 5.2 | Validated Alembic baseline:6420b89 |
| 5.3 | Atomic replay/anomaly/outbox ingestion:799cbdb |
| 5.4–5.5 | Mongo relay/idempotence/leases + device provisioning:5515caf |
| 5.6 | Authorized Flask history/page/metrics:17ffcf5 |
| 5.7 | Non-secret PG device binding/enabled + migration0003:c07c6b2 |

Последующие test/docs commits: `git log --oneline d9a000f..HEAD`; финальный хеш
указывается итоговым отчётом, а не помещается внутрь самого коммита.

## Статусы компонентов

| Компонент | Статус | Фактическая область проверки |
|---|---|---|
| Safe Git baseline / nested Ascon | существует | История сохранена, vendor/classifier этап5 не меняет |
| Publisher | проверено тестами | TLS, v2, separate keys, persistent SQLite sequence, реальный PG/Mongo приём |
| Mosquitto | проверено тестами | TLS/password/точные topic ACL; неверный пароль/CA/запрещённый read/write |
| Ingestion receiver | проверено тестами | AEAD/validation + device binding + atomic replay/anomaly/outbox; manual QoS1 ACK, PG outage и restart |
| Anti-replay | проверено тестами | PostgreSQL source of truth; rollback/concurrency/restart, consumer receiver/web |
| PostgreSQL legacy schema | проверено тестами | 14 таблиц сохранены + replay/outbox/metrics/devices/Alembic =19; legacy rows/replay сохранены |
| Alembic | проверено тестами | Empty/legacy/repeat/incompatible; composite PK не меняются |
| MongoDB | проверено тестами | Auth/scoped insert-find/read roles, validator/indexes, persistent history; restart/outage |
| Transactional Outbox | проверено тестами | claim/lease/fencing, retries/dead/requeue, retention, capacity; rollback и process crash |
| Relay | проверено тестами | Два процесса + реальная Mongo недоступность/восстановление, duplicate comparison |
| Несколько устройств | проверено тестами | Три новых отдельных identity/key/topic/history, запрет чужого topic |
| Provisioning/rotation | частично реализовано | Автоматизируемые extra-device + PG provisioning; ротация/изменение работающего состава вручную |
| Flask/roles/CSRF/Socket.IO | проверено тестами | Прежние ограничения + network HTTP/socket, logout/revocation, безопасный редирект |
| Mongo history API/page | проверено тестами | Login/role, device/date/sort/limit/offset, empty, общий503; live сохранён |
| Основной dashboard | частично реализовано | Live память50/один процесс, все устройства общие; новый history route отдельно |
| CRUD legacy | частично реализовано | Простой PUT/DELETE и allowlist; CREATE/composite CRUD не реализованы |
| Sensor_Data | существует | Схема/данные сохранены; новый pipeline пишет Mongo, не эту таблицу |
| Метрики | проверено тестами | Admin API: incoming/s, accepted/rejected/replay, backlog/age/latency/errors/retries, Mongo count |
| Ascon primitive | проверено тестами | Прежние roundtrip/tamper/KAT; исходник не изменён. Полный SP800-232 audit не заявлен |
| Notebook classifier | существует | Offline experiments; dataset/model artifacts отсутствуют |
| Автоматические проверки | проверено тестами | 210 passed без предупреждений, плюс реальные TLS/ACL/outages/crash/HTTP/socket/Chromium |
| ARM64 / Raspberry Pi execution | не проверено | Параметры TLS/native publisher готовы, физический запуск не проводился |
| 1000 msg/s / 10000 устройств | не проверено | Только будущая цель; current admission lock/count ограничивают скорость |
| FastAPI / ML inference / Policy Engine / «Магма»/CRISP | отсутствует | В этапе5 не разрабатывались |
| CI / production HA / DB TLS | отсутствует | Локальные проверки не заменяют production deployment |

## Итог проверок

- Полный актуальный pytest: **210 passed**, PostgreSQL и MongoDB реальные, без
  пропусков/предупреждений. Предыдущие177 сохранены; fixture init теперь Alembic.
- Три independently provisioned устройства и два relay; Mongo stop/recover,
  PostgreSQL stop/recover без MQTT ACK, replay/restart и процесс exit19 после Mongo
  insert до PG acknowledge — успешно, один документ на каждую стабильную identity.
- Live HTTP/Socket.IO, CSRF/roles, Mongo history/admin metrics и Chromium4 XSS
  payload — успешно; TLS/пароль/ACL negative и mqtt smoke прошли.
- Ruff, compileall, Node, uv lock, known-secret Git/image/permissions audit — успешно.
  Промежуточные неуспешные тестовые прогоны сохранены и объяснены в reports/STAGE5.md.
- Retention opt-in: проверена настройка/отключение Mongo TTL и удаление только
  delivered PG событий в tests; месячный TTL lifecycle не воспроизводился.

## Границы / следующий этап

At-least-once delivery + idempotent Mongo insert, не end-to-end exactly-once/lossless.
Конечные очереди/диск/retry budget; dead требует вмешательства. Cleanup delivered
и Mongo TTL выключены по умолчанию. Legacy FK/CRUD, Mongo HA/TLS, production HTTPS,
автоматическая ротация, многопроцессный live, большие нагрузки и ARM64 ещё впереди.

Следующий этап выполняется только по отдельной команде пользователя. ML, Policy
Engine, FastAPI и отечественный профиль автоматически не начинаются.

Тестовый lcm-stage5 остановлен обычным down без --volumes. PostgreSQL, MongoDB,
счётчики и материалы сохранены. Протокол остановки — reports/stage5-shutdown.txt.

## Этап 6 — начат, не завершён

Ветка feature/ml-inference-pipeline от cfda660. Прочитаны13 ячеек исходного
notebook, проверены preprocessing/split/labels/metrics/artifacts и доступность
сетевых признаков. Результат — ML_DATA_AUDIT.md; notebook сохранён побайтно.
Датасета DNN-EdgeIIoT и готовых моделей в исходниках нет; фактическое качество
не воспроизводилось. Скрипт audit_ml_notebook.py проверяет структуру/синтаксис
без исполнения, .gitignore дополнен форматами ML данных/артефактов.

Продолжение задания получено; после аудита начинается реализация pipeline.
В блоке аудита runtime/схема БД/безопасность не изменялись;
210 tests — исторический результат этапа5, а не новый запуск этапа6.

Блок offline ML: реализованы явные network/telemetry схемы, sklearn pipelines,
групповой/временной split, causal per-device features, statistical/IF telemetry,
RF binary/multiclass и IF IDS, manifest/hash export. 11 unit tests passed.
После получения пользовательского CSV выполнена реальная ограниченная group-based
IDS оценка; source2219201, subset11851, split5630/1227/2005. Модели/CSV локальны.
Первый текущий Docker regression run:224 passed, включая предыдущие210;
async/web интеграция ещё проверяется.

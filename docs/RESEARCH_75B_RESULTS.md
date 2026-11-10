# Этап 7.5b — результаты, границы и готовность данных

Исходный `d4dc3aa`, ветка `feature/mqtt-tls-dataset-collection`.
Реализованы isolated Compose lab,24 индивидуально provisioned устройств,
bounded generator/scenarios, NET_RAW tcpdump collector, offline tshark extractor,
connection-scoped ground truth, immutable builder, validator, disk/load watchdog,
manual retention preview и real integration/fault probe. Общие Ascon/TLS/v2/
replay/Outbox/ML/Policy исходники не менялись; добавлена только offline lab ontology.
ML-модели/артефакты этапа6 не перезаписывались, все13 baseline hashes совпадают.

Полный машиночитаемый отчёт с командами, версиями, параметрами, hashes и каждым
запуском — [stage75b-collection.json](reports/stage75b-collection.json).
Базовые неизменности — [stage75b-baseline.json](reports/stage75b-baseline.json).
Внешние источники отдельно — [EXTERNAL_DATASET_AUDIT_75B.md](EXTERNAL_DATASET_AUDIT_75B.md).

## Собранные данные

| Показатель | Результат |
|---|---:|
| Пул independently provisioned identities/passwords/Ascon keys |24/24/24|
| Максимум одновременно в основной матрице |20clients|
| Проверенный пилот |4captures,1894packets|
| Исходная основная матрица |30normal+30mixed runs|
| Повторные исправленные нарушения |10runs|
| Все основные captures / packets |70 / 53738|
| Все основные PCAP bytes / суммарная длительность генерации |15701928 /453.337s|
| Валидные captures |59:29normal+30mixed|
| Явно исключённые / quarantine |10 length-shortcut /1 invalid tcp.time_delta|
| Валидные packets / PCAP bytes / длительность |46395 /13558922 /382.945s|
| normal / controlled_violation / unknown observations |32901 /947 /12547|
| Unknown fraction |27.044%|
| Kernel capture drops |0 во всех70основных captures|
| Подтверждённые обычные QoS1 DUP reconnect connections |76|
| Peak generator process RSS |43136KiB (не всей системы)|
| Peak collector parent process RSS |23620KiB (не peak tshark child)|

Каждый run — fresh generator process, TCP/TLS sessions, client UUID и capture ID,
новое время/seed/разный subset пула или load profile. Однако общий host/kernel/
software stack означает, что **статистическая независимость не доказана**. Смена
имени capture не использовалась для искусственного увеличения групп.

Все12normal/violation scenarios реализованы; см. EXPERIMENT_SCENARIOS.md.
В mixed captures normal background сохраняет свой класс. Один mixed capture не
дал verified violation observations: неопределённость не заменялась label1.
76обычных QoS1 DUP не размечены как атаки, хотя ingestion закономерно фиксирует
replay. Replay source category сама по себе не доказывает намерение атакующего.
Валидные runs дали10175publish attempts,10041PG accepted,118PG replay и87rejected;
эти счётчики имеют разный смысл, не являются throughput benchmark всей системы.

Суммарные capture windows: все70 — 496.002s, валидные59 — 418.770s;
wall envelope основного/повторного сбора — 787.151s, включая паузы.
Это отличается от суммарного времени работы генераторов в таблице.

Ground truth: PID/socket tuple+SYN+TLS lifecycle+подтверждение исхода; margin50µs,
максимальный измеренный wall/monotonic drift1.724µs. Это измерение внутренних часов,
не абсолютная точность разметки/UTC. Нет измеренной общей accuracy label mapping.
TLS handshakes, неоднозначные границы и неподтверждённые активности остаются unknown.

## Замороженный split, без обучения

[stage75b-plan.txt](reports/stage75b-plan.txt): exit0, исходные настройки
`configs/ml/research75.json`, seed75, normal≥1000/часть, class groups≥5/часть.
Capture/session intersections0, exact feature intersections после purge0.

| Часть | Rows | Normal | ControlledViolation | Captures | Группы0/1 |
|---|---:|---:|---:|---:|---:|
| Train |6645|6452|193|36|36/17|
| Validation |2082|2025|57|12|12/7|
| Holdout |2035|1975|60|11|11/5|

Cross-partition duplicate purge удалил13796/4721/4569строк (68.2% известных
наблюдений суммарно). Это меняет prevalence, оставляет мало нарушений и ограничивает
интерпретацию будущих метрик. Неизменённый prepare_split() не обходился random split.
Пилотный strict plan отвергнут с support4/2; это ожидаемая защита методики.

Frozen plan: `.local-runtime/stand75b/plan.json`, файл read-only400, внутренний SHA256
`2a08ab6ee0689d67015db109d3b85740b0a2c9d61ffb1e5428e1b72cc9f4f54a`.
Private dataset и manifest: `.local-runtime/stand75b/dataset/`.
Raw captures: `.local-runtime/stand75b/primary/`, права700/600, вне Git/образов.
Новый RF/IF **не обучался**, final holdout не оценивался, thresholds не подбирались,
новых precision/recall/FPR/ROC/PR-AUC нет. Synthetic unit fixtures не являются
результатами исследования реальных атак.

## Фактические проверки

- [stage75b-tests-final.txt](reports/stage75b-tests-final.txt):301pytest passed,
  включая прежние267 и34новых; PostgreSQL/MongoDB реальные, тестовые schemas и
  отдельный `lcm-stage7b-regression`, без skips в контейнерном прогоне.
- Локальный запуск без TEST_DATABASE_URL ранее:203passed/87skipped. Это не полный
  результат; окончательный real-container прогон проверяет пропущенные сценарии.
- [stage75b-storage.txt](reports/stage75b-storage.txt):PG/Mongo outage recovery,
  rollback/replay, несколько устройств, crash после Mongo write перед PG ACK,
  параллельные relays/restarts, без потери подтверждённых событий в этих сценариях.
- [stage75b-ml.txt](reports/stage75b-ml.txt):прежний DEMO artifact, missing model,
  reload/dedupe/Mongo recovery; новых моделей из генератора не устанавливалось.
- [stage75b-policy.txt](reports/stage75b-policy.txt):два workers, restart/PG outage,
  DRY_RUN, нет applied configuration; неизменная ML trust boundary.
- [stage75b-security.txt](reports/stage75b-security.txt):trusted/untrusted CA,
  wrong password, deny write/read по ACL. TLS не отключался.
- [stage75b-web.txt](reports/stage75b-web.txt):live CSRF/roles/safe redirect/CORS/
  Socket.IO/history/ML/Policy authorization.
- [stage75b-browser.txt](reports/stage75b-browser.txt):реальный Chromium,12 XSS probes.
- [stage75b-validation.txt](reports/stage75b-validation.txt):output/source hashes,
  unknown exclusion, source mapping, input schema и private provenance.
- [stage75b-secrets.txt](reports/stage75b-secrets.txt):Git history/working tree,
  private input modes и3Docker images, без известных настоящих секретов/PCAP/models.
- [stage75b-static.txt](reports/stage75b-static.txt):ruff src/tests/scripts.

Real lab probe:24разных passwords/keys;12714Mongo records равны12714PG outbox
на момент probe; pending0; replay/rejected события существуют, rejected device ID
пустой; Policy DRY_RUN, applied0. Затем намеренная ранняя остановка collector:
generator остановился за2.185s, все клиенты закрыты, established TCP connections0,
ещё52принятых измерения дошли до Mongo. Неудачный capture не включён в dataset.
ML в collecting lab выключен; отдельный real ML regression проверен на собственном
контуре. Непрерывность *активного* ML worker одновременно с collector fault в одном
проекте отдельно не измерялась.

## Ошибки и ограничения

Первый пилот до PG provisioning давал rejected telemetry: сохранён отдельно и не
включён в scientific data. Исправлена startup dependency research-provision.
Промежуточная некорректная Compose YAML и syntax error orchestrator обнаружены
проверками; история сохранена, syntax fix отдельным e9d3241. Логи неуспеха/повторной
успешной проверки — stage75b-unit-research.txt. Текущие тесты проходят.

Свои label/config shortcuts выявлены до обучения и документированы; исправленные
нарушения собраны позднее, поэтому batch/host scheduling всё ещё возможный confound.
Не доказаны переносимость на физические IoT/ARM/другой kernel, real attacks и
отсутствие shortcut learning. Внешние наборы не импортировались/не смешивались.
Password reject не подтверждает device identity; local tamper+aggregate server
reject слабее per-packet independent server audit. IPv6/другой linktype не проверены.

CPU/RAM контейнеров ограничены жёстко. Disk/load budgets останавливают генерацию
watchdog, но не заменяют filesystem quota/отдельную VM. Не измерены peak RSS tshark,
абсолютная точность часов и capacity всей системы. Logs/PCAP/retention контролируются,
автоматического удаления предыдущих данных нет. Накопление PostgreSQL/Mongo внутри
стенда не делает их источником ML-датасета: сеть/ground truth хранятся отдельно.

## Следующий этап только по команде

Структурные gates выполнены: набор пригоден для **ограниченного лабораторного**
RF/IF эксперимента7.5c с замороженным holdout. Научная оценка реального обнаружения
атак не подтверждена. Перед обучением утвердить scope/curation, per-scenario
оценку, доверительные интервалы при5positive holdout groups и отдельный внешний
совместимый источник. Для доверенного online IDS нужны новый collector/source
contract, независимые реальные размеченные данные и отдельная валидация.

Команды свежего запуска — DATASET_COLLECTION.md. Реальные команды этого запуска
сохранены в stage75b-collection.json. Для воспроизведения анализа существующих
данных используйте dataset validate и research cli plan с новым output path;
не перезаписывайте исходный план. На7.5b перехода к train/test, FastAPI, Policy
управлению, «Магме»/CRISP и массовой нагрузке не было. Push/merge не выполнялись.

## Завершение хранения и проверки воспроизводимости

Офлайн rebuild выполнен с1CPU/768MiB и без сети: dataset.csv, observations.csv
и dataset.manifest.json имеют **идентичные SHA-256** исходной замороженной версии
([stage75b-bounded-rebuild.txt](reports/stage75b-bounded-rebuild.txt)).
Новых captures/обучения при этом нет. Права исходного research-data volume
приведены к0700dirs/0600files; extractor теперь сам устанавливает umask077
([stage75b-permissions.txt](reports/stage75b-permissions.txt)).

Контуры lcm-stage7b-lab и lcm-stage7b-regression остановлены без удаления volumes.
Повторный запуск PG/Mongo для финального pytest также завершён down без -v;
[stage75b-shutdown.txt](reports/stage75b-shutdown.txt). Результат Docker inspect
изоляции/quotas — stage75b-isolation.json. Предыдущие volumes/модели не удалялись.

APT tool versions записаны в каждом capture manifest, но Debian repositories не
закреплены snapshot-lock: для будущей повторной extraction на другом хосте нужно
сравнить tool версии и hashes; byte-identical повтор самой сетевой генерации не
обещается. Private исходники/модели и файловые права сохранены.

Git этапа:8198f11 — isolated lab;447dec0 — provenance/guards (промежуточная
syntax ошибка);e9d3241 — исправление; e2c5b17 — length shortcuts/curation/private
exports. Итоговый docs commit указан в финальном отчёте пользователя.
Полный список изменений: [stage75b-files.txt](reports/stage75b-files.txt).

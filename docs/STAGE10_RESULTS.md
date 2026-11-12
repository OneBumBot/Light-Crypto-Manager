# Этап 10 — производительность, надёжность и подготовка ГОСТ

Работа выполнена в `feature/system-performance-validation` от `feature/system-integration-demo`, исходный SHA `4ac5081a69199041fb8e34111b976da6c257ac93`. Проверенная версия приложения перед итоговыми отчётами — `e3a6e47`. Версии каждого эксперимента, состояние рабочего дерева и Docker image IDs сохранены в JSON. Полный baseline после последних изменений UI: **715 passed, 0 skipped, exit 0**. Итоговая регрессия: **739 passed, 0 skipped, exit 0**, 37,35 с; после исправления ограничения логов выполнен дополнительный полный запуск, его журнал — `reports/stage10/final-regression-after-compose.txt`.

Выполнен только этап 10. Policy работает в `DRY_RUN`, управление — только `MANUAL_AUTHORIZED_CONTROL`. RF/IF остаются исследовательскими, `trusted_detector=false`. Новые алгоритмы не включены. Main, push, merge и rebase не затронуты. Количество тестов не является доказательством качества IDS или защищённости production-развёртывания.

## Измеренная нагрузка

Созданы четыре независимых проекта `lcm-stage10-performance-{base,small,medium,extended}`: отдельные CA, MQTT credentials, ключи Ascon/AES/HMAC, PostgreSQL/MongoDB volumes и SQLite ledger каждого устройства. Всего подготовлено 88 identities в разных пространствах проектов; одновременно работало не более 50 программных агентов. Использованное состояние SQLite не клонировалось.

Основные окна выполнялись последовательно при целевой частоте два сообщения в секунду на устройство. Все величины ниже измерены; PUBACK относится к брокеру, а admission — к PostgreSQL.

| Устройств | Окно,s | Scheduled | Formed / publish / queued | PUBACK в окне | PG admission в окне | Formed→PG после drain | msg/s |
|---:|---:|---:|---:|---:|---:|---:|---:|
|3|300.17|1800|1790 / 1790 / 1790|1790|1790|1790/1790|5.96|
|10|300.94|6018|5980 / 5980 / 5980|5980|5980|5980/5980|19.87|
|25|900.00|45000|44716 / 44716 / 44716|44716|44716|44716/44716|49.68|
|50|300.00|29999|29818 / 29818 / 29818|29816|29815|29818/29818|99.38|

`Scheduled` — периодические возможности отправки по часам агента; `formed` — реально сформированный AEAD-пакет. Разница между ними относится к программному планировщику и ожиданиям, а не к потере уже сформированных сообщений. Для 50 устройств три admission произошли после границы основного окна; два PUBACK не попали в окно наблюдения callback. Все 29 818 сформированных пакетов найдены в PG после drain. Нельзя считать разницу границ окна потерей или приравнивать PUBACK к durable commit.

| Устройств | CPU mean,% одного core | RAM mean,MiB | median measured→received,ms | median / p95 / p99 measured→delivery finish,ms |
|---:|---:|---:|---:|---:|
|3|31.4|621|3.17|264.2 / 488.5 / 508.6|
|10|61.6|699|2.96|265.1 / 489.9 / 509.8|
|25|124.9|1133|3.22|269.7 / 493.8 / 520.6|
|50|179.0|1658|10.19|287.2 / 509.9 / 558.9|

В таблице CPU/RAM приведены средние, а в соответствующих графиках — медианы sampled values. CPU указан в процентах одного ядра и суммирован по контейнерам проекта; RAM — Docker working set. Хост: 16 логических CPU, около 31 ГиБ RAM, общий Linux kernel контейнеров и collector. Полные версии Python, OpenSSL, пакетов и параметры PostgreSQL находятся в `environment.json`.

`measured→received` включает формирование, очередь, транспорт и проверку до timestamp admission. `delivered_at` ставится в PG после Mongo majority/journal write. Точное время PG commit, отдельная сетевая задержка и timestamp Mongo commit **не измерены**. Percentiles описывают зависимые сообщения конкретного прогона, а не доверительный интервал независимых развёртываний.

Сравнение описательное: длительности и объёмы накопленной истории различаются. Окно трёх устройств включало браузерные переключения и microbenchmark; в окне 25 устройств были ограниченные диагностические запросы и целевая проверка в отдельной SQL schema. Пики ресурсов не исключались. Графики не содержат экстраполяции максимальной вместимости.

Пятнадцатиминутная стабильность проверена на 25 устройствах; 30 минут не измерялись. Небольшой текущий Outbox сохранялся без неограниченного роста. Проверка не доказывает отсутствие утечек памяти на произвольно долгом интервале. Рабочие значения датчиков — сообщения существующего software agent; это реальные криптографические/транспортные операции, но не физические измерения Raspberry Pi.

## Ascon и AES, частоты отправки

Microbenchmark: 24 независимые серии в отдельных процессах — три повтора, размеры 64/256/1024 и типичные 83 байта sensor JSON, две реализации. На серию: 100 прогревочных и 1000 измеряемых пар encrypt/decrypt, одинаковый AAD 148 байт, чередование порядка и новые временные ключи. Сохранены исходные наносекунды, CPU time, RSS, throughput, ciphertext size и описательная статистика по сообщениям и независимым повторам.

Медианы шифрования 83 байт: Ascon — 286,544 / 285,848 / 287,701 мкс; AES — 1,072 / 1,072 / 1,072 мкс. Это сравнение **Python reference Ascon и native cryptography AESGCM на данном x86**, а не универсальная эффективность математических алгоритмов, криптостойкость, ARM или энергопотребление. RSS относится ко всему процессу. Доверительные интервалы по трём независимым повторам не оцениваются.

Дополнительно выполнены 60-секундные окна одного активного агента: Ascon 2 Гц, AES 2 Гц, Ascon 1 Гц и 0,5 Гц. Сформировано соответственно 119, 119, 59 и 29 пакетов; все найдены после drain. Изменение фазы относительно паузы relay 0,5 с влияет на задержку. Короткие окна не заменяют длительную проверку устойчивости; полная матрица N×rate не исследована.

## Переключения и итоговая доставка

| Project | PG committed total | Mongo managed total | Transitions / confirmed | Authenticated ACK | Immutable effective receipts |
|---|---:|---:|---:|---:|---:|
|lcm-stage10-performance-base|5307|5307|20 / 20|37|23|
|lcm-stage10-performance-small|23023|23023|10 / 10|20|20|
|lcm-stage10-performance-medium|50661|50661|8 / 8|16|33|
|lcm-stage10-performance-extended|30877|30877|0 / 0|0|50|

Итого: **109 868 PG admissions и 109 868 Mongo records; 38 из 38 переходов подтверждены, 73 authenticated ACK и 126 immutable receipts. Итоговые pending/dead и UNKNOWN — 0.** Это суммы независимых проектов, а не показатели одного production-сервера. Число ACK меньше удвоенного числа переходов из-за намеренных сценариев потери ACTIVATE ACK; effective подтверждалось новой AEAD-телеметрией.

После остановки контейнеров вслед за браузерными проверками оставались 35 durable Outbox records. Их доставка после запуска только storage/relay подтверждена в `shutdown-outbox-resume.json`; число admissions не изменилось. Наличие очереди до drain не названо потерей. `stop` сохраняет очередь; обязательный drain при недоступной Mongo не обещается.

На 25 устройствах выполнены шесть переходов, включая одновременные переходы разных устройств, и два переключения из Chromium. Соседние устройства и capabilities gamma не изменились. Время request→наблюдаемое клиентом effective: 1,14–1,23 с. PG `created_at`→ACK: 0,155–0,453 с; `created_at`→timestamp confirmation: 0,164–0,687 с. Наблюдение с polling отделено от серверных timestamps; точный commit timestamp не измерен. Пауза перед запросом соблюдает действующий двухсекундный limiter и не входит во время от запроса.

HTTP 202 и ACK отдельно от effective. Завершение требует сохранённого receipt новой принятой телеметрии целевого AEAD. Никаких фиктивных ACK или автоматического выбора профиля по Policy/ML нет.

## Отказы и восстановление

При десяти одновременно передающих агентах последовательно проверены MongoDB, Control Worker, Policy Worker, PostgreSQL, broker, Device Agent и receiver. Сохранены начало, возврат сервиса, before/during/after counters, очередь и effective state.

Верхние оценки времени наблюдаемого drain после запуска сервиса: Mongo — 15,48 с; control — 34,21 с; policy — 10,77 с; PG — 24,84 с; broker — 1,33 с; устройство — 17,71 с; receiver — 6,07 с. Эти числа включают ожидание пустой очереди при продолжающемся входе ранней версией checker; это не точный service RTO. Окончательный checker проверяет доставку записей до watermark, не требуя постоянно нулевой очереди.

Полный дополнительный source census двух fault-cohorts сопоставил 26 607 сформированных агентами пакетов с PG: неподтверждённых identities — 0. В семи интервалах от начала остановки до возврата сервиса сформировано/найдено соответственно: Mongo 481/481, control 346/346, policy 781/781, PG 240/240, broker 33/33, device 226/226, receiver 210/210. Журнал line-buffered, поэтому это доказательство по сохранённой наблюдаемой совокупности, а не гарантия учёта события при произвольной аварии до записи journal. Ранний неинструментированный прогрев в исходную совокупность не включён. Полные timestamps и identities hashes — `fault-source-census.json` и `fault-source-intervals.json`.

В основных окнах reconnect агентов — 0. В полном журнале десяти агентов найдено 20 reconnect того же процесса, включая отдельный broker outage браузерного journey; намеренные stop/recreate сюда не включены. DB reconnect count не измерен. Максимальные наблюдавшиеся Outbox backlog: 3/10/25/52; PG connections: 11/8/9/11. Рост working memory за окна: 596→617 / 647→721 / 989→1191 / 1563→1700 MiB. Эти значения не доказывают отсутствие долгосрочной утечки; caches/history и фоновые probes различаются.

Также повторены девять прежних настоящих recovery-сценариев: restart устройства на AES, отказ при восстановлении устаревшей SQLite, restart worker после PREPARE, потеря ACTIVATE ACK, broker outage, PG outage после intent и после применения устройством, grace expiry с ручной reconciliation, потеря SQLite. Все прошли. При потерянном состоянии agent завершился с exit 1 и не передавал новую принятую телеметрию — ожидаемый fail-closed результат. UNKNOWN_OUTCOME и необходимость новой аутентифицированной телеметрии сохранены; silent downgrade и произвольный reset отсутствуют.

## Найденные ошибки и ограничения

1. **HTTP 500 при недоступности PG во время загрузки пользователя.** Ошибка происходила до monitoring handler. Теперь SQLAlchemyError даёт 503, сессия сохраняется, непроверенные права не заменяются анонимными или закешированными. Есть точная регрессия и mutation oracle.
2. **Policy не успевает за 25×2 Гц и 50×2 Гц.** Default batch 32 с паузой 1 с задаёт верхнюю оценку около 32 событий/с ещё до SQL. Растущий поиск через consumed prefix дополнительно снижает скорость. В промежуточной пробе: 11 723 observations, 6120 обработаны, 5603 pending, lag 112,697 с. Максимальный записанный lag внутри нагрузочных окон: 1,019 с для 10 устройств, 296,673 с для 25 и 231,572 с для 50. После дополнительных UX-сценариев pending достиг 29 481 / 21 954. Приём телеметрии работает, но свежесть всего контура Policy на этих нагрузках не обеспечена.
3. **Свежий heartbeat скрывал старые источники Policy.** Реальный API возвращал `stale=false` при последнем учтённом событии старше 207 с. Read model теперь проверяет время события и TTL правил; missing/future также означают stale. Четыре SQL negative cases и настоящий Chromium при 50 устройствах подтверждают исправление. FSM и DRY_RUN не изменены.
4. **Ошибка checker: слишком быстрый обратный request.** Сервер правильно вернул 409 по limiter. Исправлена частота checker, профиль восстановлен обычной авторизованной командой. Новый диагностический GROUP BY первоначально дал GroupingError из-за двух bind expressions; исправлено переиспользованием выражения, добавлена реальная PG-регрессия с Ascon/AES admission.
5. **Relay не имеет права listIndexes.** Это ожидаемая защита. EXPLAIN получен отдельной лабораторной admin-диагностикой через password file внутри Mongo; права рабочих ролей не расширялись.
6. **Отсутствовал logging limit Policy в resource overlay.** Добавлен json-file 5m×2 и проверен HostConfig остановленных тестовых контейнеров. Предыдущие короткие журналы измерены; не заявляется, что cap был установлен во время первоначальных окон.
7. **Внутренний риск старого poison producer.** Выбор max(admitted)+1 внутри старого grant мог пересечься с formed-but-unadmitted AES packet. Реальная коллизия не воспроизводилась; это не объявляется сетевой уязвимостью production agent. Probe теперь получает новый authenticated MQTT lease_grant, не меняя nonce construction рабочего устройства.

Новых SQL migrations или индексов нет. Фактические 26 SELECT карточки дали максимум 29,868 / 19,842 мс на измеренных snapshots; Mongo history возвращает 50 записей при 50 examined keys/docs. Это не измерение полного PG transaction throughput. Подробные планы, ограничения и дальнейшие варианты — `STAGE10_BOTTLENECK_ANALYSIS.md`.

## Проверки безопасности

Настоящий MQTT/TLS poison test: 17 malformed пакетов Ascon и 17 AES безопасно отвергнуты; replay/effective/evidence/Outbox/Mongo не изменены. Корректные пакеты после них и соседнее устройство доставлены. Poison не вызвал processing failures или reconnect; ограниченное наблюдение и explicit receiver restart не выявили повторной доставки poison. PUBACK не использован как доказательство manual application ACK. Unit oracle требует disconnect/no ACK при PG commit или reject-audit commit failure; реальные recovery-сценарии дополняют эту проверку.

Под нагрузкой 25 устройств повторены захваченные байты настоящих пакетов обоих AEAD: unique admission остаётся один, effective не меняется. Проверены отказ неправильному паролю, недоверенной CA, чужому topic и публикации от reader. HTTP проверяет pagination/identity/limits, viewer/operator 403, missing CSRF 400, unknown device 404, gamma AES 409 и draft ГОСТ 409. Отрицательные запросы не создали transitions/receipts; настоящие ключи в проверенных API не найдены.

Chromium: отдельная криптостраница на 3 и 25 устройствах, полный Stage 9 journey на 10, реальный Policy backlog на 50; desktop/mobile/reload, настоящие двусторонние переключения, outages, XSS/malformed/cross-device boundaries. Перехваченные ответы применялись только для явно помеченных DOM fixtures, отдельно от доказательств MQTT/SQL.

Мутации: 14 прежних control, 10 server/read-model и 3 Chromium DOM — **все 27 выявлены поведенчески**. Для каждой сохранены injected defect, тест, expected/actual failure и exit code. Ошибки синтаксиса, импортов и зависимостей не засчитывались. Полный suite сохраняет KAT Ascon/AES, telemetry/poison/replay/nonce, Outbox/Mongo/HMAC/recovery, DRY_RUN/untrusted ML, RBAC/CSRF/Socket.IO/XSS и Ground Truth v2.2.

## Российская криптография и этап 11

Исследованы ГОСТ Р 34.12-2015, RFC 7801/8891 и MGM RFC 9058. Кузнечик: блок 128 бит, ключ 256; Магма: 64/256. MGM требует уникального ICN длиной n−1 бит, фиксированного tag и собственных ограничений длин/usage. AES-GCM nonce нельзя переносить автоматически. Параметры, формулы, риски и источники — `RUSSIAN_CRYPTO_INTEGRATION_DESIGN.md`.

Рассмотрены gostcrypto (Python/MIT, MGM отсутствует в изученном API), tarantool/go-gostcrypto (Go MGM64/128, BSD2), gost-engine (OpenSSL/Apache2). PyGOST/GoGOST upstream через текущий инструмент не верифицирован. Ни одна библиотека не объявлена production-ready или сертифицированной. Нужны block vectors RFC 7801/8891, MGM Appendix A, второй независимый implementation и реальные negative tests; Python binding и ARM ещё не проверены.

Архитектурный план Kuznyechik-MGM готов, реализация не начата. Magma-MGM для live pipeline пока не обоснован: 64-битные bounds могут требовать бюджета намного меньше нынешнего grant 10 000. Требуются отдельный durable per-key usage accounting и, возможно, versioned lease migration. Текущий dispatch `if AES / else Ascon` нельзя расширять третьей записью; сначала нужны explicit provider mapping и однозначные versioned wire names. Draft metadata не даёт права активации. План сравнения реализаций — `CRYPTO_PROFILE_COMPARATIVE_EXPERIMENT_PLAN.md`.

## Сохранность и воспроизведение

Проверены 378 tracked historical hashes и 764 файла локального исследовательского архива: изменений нет. Проверены независимость новых ключей, права private files, конкретные новые secrets в Git/отчётах и runtime images; совпадений нет. Это инженерная проверка заданных значений и build allowlist, не внешний аудит. Main сохранён на `c352d817386a17fb244d3567b287af0412eed4e4`.

Все созданные сервисы остановлены без удаления volumes. Настоящие положительные TCP probes внутри своих Docker networks и отрицательные cross-project probes в обе стороны прошли (`network-isolation.json`). Private inputs сохранены на устойчивом диске: `.local-runtime/stage10/private/lcm-stage10-performance-{base,small,medium,extended}`; исходные `/tmp` copies также оставлены. Настоящий ledger находится в именованном device volume, а не в исходном seed SQLite. Resume возможен только с исходными SQL/device volumes и ключами; отсутствие used volume вызывает отказ.

```bash
# Новый отдельный стенд:
.venv/bin/python -m scripts.performance_lab prepare \
  --directory .local-runtime/stage10/my-10 \
  --project lcm-stage10-performance-my-10 --devices 10
.venv/bin/python -m scripts.performance_lab start \
  --directory .local-runtime/stage10/my-10 --build
# Ограниченный прогон с новым output path:
timeout 480 .venv/bin/python -m scripts.performance_run \
  --directory .local-runtime/stage10/my-10 --seconds 300 \
  --output .local-runtime/stage10/reports/my-10-run1
# Stop сохраняет очередь, keys и counters:
.venv/bin/python -m scripts.performance_lab stop \
  --directory .local-runtime/stage10/my-10
```

Для продолжения уже созданного стенда использовать `start` с его сохранённым private directory, без нового `prepare`. Учётная запись `demo-admin`, случайный пароль — в private `accounts/admin.password`, не в Git. Полные требования, команды, watchdog, интервалы, exit codes и сценарии — `STAGE10_LOAD_TEST_PLAN.md` и JSON command ledgers.

Исходные JSON/CSV сохранены lossless gzip с SHA256 manifest (`raw-artifacts.json`); локальные рабочие копии не удалены. Есть per-device/per-run анализ и восемь PNG-графиков только по измеренным данным. Список изменённых файлов — `reports/stage10/changed-files.txt`. Исторические PCAP, datasets, models, frozen plans, ключи и результаты прежних этапов не заменялись; RF/IF training и изменение holdout не выполнялись.

Оставшиеся ограничения: один прогон на cohort, неполная матрица частот, software x86 вместо физических IoT, отсутствие 30-минутного теста, точного commit/network-only timing и production HTTPS/backup/rotation. Число 50 — проверенный режим telemetry path, не максимальная вместимость всей системы: Policy freshness уже нарушается на 25×2 Гц. На этапе 11 нужны проверяемый provider, независимые KAT, usage/nonce reservation, versioned provisioning/dispatch/recovery и реальные двусторонние TLS-переходы. Автоматическое управление по исследовательскому ML не допускается.

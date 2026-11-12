# Этап 10: измеренные ограничения

* Проверены software x86 identities, не физические Raspberry Pi. Максимальная
  вместимость не установлена; 50×2 Гц — пятиминутное подтверждённое окно telemetry.
* Default Policy batch32 + sleep1s и поиск consumed prefix не успевают за 25/50×2 Гц.
  Свежий heartbeat не гарантирует свежие источники; UI теперь явно помечает stale
  evidence. Policy DRY_RUN, автоматических crypto commands нет.
* Один run на cohort; неполная матрица частот, разные durations/истории/probes.
  Нет 30-минутного результата, ARM/энергии и точного PG/Mongo commit timing.
* Retention отключён. Security observation journal ограничен 100000 записями;
  при исчерпании растёт overflow, что не является полным аудитом новых событий.
  Обслуживание/архивирование/backup требуют отдельной эксплуатационной политики.
* Одновременная остановка consumers может оставить durable Outbox pending.
  Stop сохраняет данные, но не обещает drain при недоступной Mongo. Resume relay
  доставил наблюдавшиеся 35 записей; только после drain сравнивать PG/Mongo totals.
* MGM не готов к активации. Magma64-bit usage bounds и grant10000 несовместимы
  по умолчанию; binding/ARM/KAT/usage accounting ещё не реализованы. Нельзя просто
  добавить descriptor в нынешний ifAES/elseAscon dispatch.
* Private inputs новых стендов сохранены в `.local-runtime/stage10/private/`.
  Использовать вместе с исходными SQL/device volumes; seed SQLite не заменяет ledger.

Подробности и реальные источники: [STAGE10_RESULTS.md](STAGE10_RESULTS.md).
Ниже сохранена история ограничений предыдущих этапов.

# Stage 9: текущие ограничения

* Software agents/x86_64, не physical Raspberry Pi и не production server.
* Polling каждые 3 s: быстрые промежуточные фазы могут быть видны только через
  durable audit; HTTP 202/ACK не означают effective.
* Recent telemetry ≤15 s — admission freshness, не broker presence. Diagnostic
  heartbeat не является криптографическим свидетельством устройства.
* Policy recommendation stale при старом state/worker; ML missing не означает
  норму. Политика остаётся DRY_RUN, research scores не дают actuation rights.
* Histories ограничены, inventory paginated; большие production объёмы/retention
  и query plans требуют отдельной эксплуатационной оценки.
* Last receiver/worker heartbeat хранится, полная история component uptime и
  прежних успешных Mongo probes не хранится. При отсутствии evidence — unknown.
* Flask dev HTTP только loopback. Production TLS proxy/session deployment,
  backup/restore/rotation и physical-device benchmarks требуют следующего этапа.
* PREPARE-only expiry/lost SQLite/joint authority rollback сохраняют ограничения
  CONTROL_RECOVERY.md; dashboard не добавляет небезопасный reset.
* Lab TLS CA/server certificates выдаются на 30 дней; поздний resume требует
  reviewed renewal либо нового независимого стенда, без отключения TLS.
* Advanced legacy pages сохраняют прежние JSON diagnostics/CDN dependencies;
  основной Stage 9 dashboard/nav/native charts работают без CDN.

Найденные и исправленные integration/harness ошибки, включая installer legacy
assumptions/private account transfer и browser fixture callback, описаны в
STAGE9_RESULTS.md; прежние неуспешные журналы не удалялись.

# Уточнение 8-fix

Подтверждён и исправлен внешний TypeError на unhashable outer profile (list/dict).
В изолированном MQTT/TLS baseline наблюдались повторные доставки и подключения;
после exact-type guard соответствующие негативные сценарии проходят. Подробности
и границы выводов — STAGE8_FIX_RESULTS.md. Аналогичных подтверждённых сетевых
ошибок типа в control paths аудит не выявил; прямые внутренние API и повреждённый
приватный provisioning не считаются произвольным MQTT input.

PREPARE-only expiry всё ещё блокирует admission: безопасного CANCEL/reset endpoint
нет. UNKNOWN_OUTCOME при возможном ACTIVATE сохраняется; нужен оператор и новая
аутентифицированная целевая telemetry в bounded reconcile window. Действия и
необходимые доказательства описаны в CONTROL_RECOVERY.md. Нельзя сбрасывать nonce/
replay/ledger или молча возвращать старый профиль.

Первый 8-fix regression выявил нестабильное ожидание старого ML-storage теста:
конкурентный claim допускает временный None. Тест теперь bounded polls как worker,
проверяя все восемь уникальных claims и прежний fencing; ML runtime не изменён.
RESEARCH/DEMO, trusted_detector=false и Policy DRY_RUN сохранены. Software/x86,
короткие окна наблюдения, preprovisioned keys и отсутствие внешнего pentest остаются
ограничениями; число прошедших тестов само по себе не доказывает защищённость.

# Актуальное уточнение этапа 8

Устранены Ascon-only dispatch, отсутствие real device control, отсутствие
telemetry-confirmed effective и missing durable crypto receipts. Реальные новые
дефекты этапа (status length, Unicode MAC, late ACK metadata, retention reference)
исправлены с отрицательными/PG/network tests; подробности STAGE8_RESULTS.md.

Оставшиеся ограничения: software agents/x86_64, без ARM/hardware tests; HMAC control
не шифрует metadata от broker; keys предварительно provisioned. Новый boot/range
exhaustion требуют доступную PG/control authority; joint snapshot rollback
требует новую epoch. PREPARE-only expiry/missing ledger не имеют универсального
автоматического remote repair. Device outgoing queue не durable, не обещается
lossless/exactly-once. Audit append-only на уровне приложения, владелец БД trusted.

RF/IF научная достоверность/недостаточность dataset 7.5b-fix не исправлялись:
RESEARCH/DEMO, trusted_detector=false, Policy DRY_RUN. «Магма»/CRISP/FastAPI и
автоматическая ML actuation отсутствуют. Исторические проблемы/результаты ниже
сохранены; «только Ascon/нет live channel» относятся к прошлым этапам.

# Ограничения этапа 7.5

Научный RF/IF benchmark новых данных заблокирован. MQTTset raw имеет только один
normal capture; reduced330926 rows потерял provenance и содержит209499 одинаковых
reduced rows (не обязательно те же физические пакеты). IEEE page metadata доступна,
но архивы download UI требуют login/subscription; данные не получены/не обойдены.

Frozen RF diagnosis: до purge normal validation694, после9,1 group/1 vector,
risk1.0; threshold>1 не детектирует атаки. IF overall recall.4945 скрывает
нулевой recall ICMP/UDP и высокий MITM recall на old limited test. Это не новое
подтверждение качества или независимая оценка. Stage6 reports/models не менялись.

Новая engineering схема5 TCP features видима под TLS в принципе, но offline
extractor не равен runtime collector. Требуются agreed link layer/clock/stream
semantics, trusted broker/identity adapter и новые TLS captures. Native2020 packet
CSV/uni/biflow нельзя искусственно zero-fill или считать одной гранулярностью.

Conservative feature-fingerprint purge может удалить нормальные repeated patterns;
потери и counts до/после фиксируются, insufficient support приводит к отказу.
Capture IDs не доказывают независимость; group CI имеет ограничения zero-event
bootstrap. Operating point empirical5% не population guarantee. Final-test marker
преднамеренно блокирует повтор даже после crash; recovery — reviewed new experiment.
External route оценивает binary risk, не объединяет source-specific attack taxonomies.

Новых real-data model artifacts нет. Classifier tests обучают только явно synthetic
DEMO fixtures. Baseline inference timing на old validation — snapshot общегоx86_64
host, cumulative process RSS, без нового training/ARM64/load/энергии. Dataset/weights
лицензии не переносить на код/статьи или наоборот; raw/weights не публикуются.
Policy/crypto/TLS/replay/Outbox/Mongo/Flask invariants сохранены. Ниже история7.

---

# Актуальные ограничения после этапа 7

Устранены: отсутствие Policy Signal/версий политики/FSM/PG аудита, отсутствие
bounded source journal и отдельного DRY_RUN worker, смешение рекомендации с
подтверждённым применением. Формальный control contract и simulator отделены от
реального device state. Все текущие модели остаются DEMO/RESEARCH и недоверенными.

Открытые ограничения:

- Реальное управление отсутствует: нет device-side handler, live control keys,
  signatures/AEAD control envelope, device ACK и криптографического переключения.
  Applied Configuration остаётся NULL. Ascon — единственный реализованный профиль.
- security_violation критического уровня проверяется контролируемыми тестами и
  симуляцией; реального trusted online источника пока нет. Broker auth/ACL logs
  не подключены. InvalidTelemetry даёт общий rejected, без точной причины отказа.
- QoS1 дубликаты могут дать replay evidence; это не доказательство атаки. Thresholds
  и cooldown — экспериментальная политика, не научно подтверждённый детектор.
- ML quality и trusted_detector=false не менялись. Initial NORMAL и восстановление
  требуют свежего scored ML, поэтому без доступной модели UNKNOWN ожидаем.
- Security journal finite100000; при заполнении overflow теряет policy coverage
  явно. Очистка только явная, до1000 старых уже обработанных строк за вызов.
  Прошлые Anomalies и история до cutover автоматически не backfilled.
- Audit retention по умолчанию отсутствует. Явная очистка удаляет старые decisions/
  transitions и terminal intents, обезличивает payload учтённых signals, оставляя
  identity tombstones против повторной обработки. Это не полный архив исходных
  оснований после явной очистки; перед ней нужен собственный архив. Политики,
  tombstones, signals без decision (rate_limited/unattributed), admin audit и states
  автоматически не удаляются; нужен capacity plan.
- Retention ограничивает replay старых данных для новой версии политики. Гарантия
  полных исторических рекомендаций отсутствует. Late evidence аудируется, не
  применяется ретроспективно; Source processing не end-to-end exactly-once.
- Pending proposal expiry обрабатывается bounded idle pass; большой backlog может
  задержать обновление status, expires_at нужно проверять независимо. Requested
  state хранит исторический contract, актуальный статус — в intents.
- SELECT aggregates и anti-joins требуют дальнейших нагрузочных измерений. Текущие
  batch32, evidence128, memory256MiB не доказывают1000msg/s или10000 устройств.
- Source journal capacity lock добавляет PG работу в ingestion transaction. Старый
  admission lock не оптимизировался. Shared PG role, внутренний DB TLS/HA и прочие
  технические ограничения предыдущих этапов остаются.

Результаты: POLICY_EVALUATION.md и reports/STAGE7.md. Ниже сохранены исторические
аудиты; их заявления «Policy Engine отсутствует» относятся к соответствующим этапам.

---

# Актуальные ограничения после этапа 6

Исторические аудиты ниже сохраняются; актуальные ML факты имеют приоритет.

Устранены: notebook-only workflow без persisted preprocessing, random-row fallback
в новом training, отсутствие ML feed/worker/events и авторизованного представления.
Notebook неизменён; его старые методические проблемы не «починены» переписыванием
исследовательского материала. Новые модули — src/classifier/ml и src/ml_storage.py.

Открытые научные ограничения:

- Реальная Edge оценка только на fixed subset11851 и grouped/proxy holdout:
  train5630/val1227/test2005, val normal9, train7 из15 categories, unseen MITM в test.
  RF binary threshold>1 и recall0; RF multiclass false positives велики. Это не
  доверенный attack detector; per-device/session переносимость не подтверждена.
- Подтверждены label proxies0/0.0 в четырёх исходных Edge полях; core их исключает,
  но это не независимый аудит всех remaining protocol semantics. Некоторые DNS
  boolean fields и ports некорректны/неоднозначны. Полная chronology не установлена.
- Full CSV C-engine auditor разово завершился SIGSEGV; raw-string Python engine
  audit успешен. Реальные модели обучены на ограниченном prepared CSV. Не заявляем
  успешное full2.2M-row RF обучение. License local data/weights не подтверждена;
  они не публикуются. Новые датасеты только подобраны (ML_DATASETS.md).
- Telemetry training — synthetic DEMO (320 records,4 devices), не реальные normal
  conditions. Прогнозы/старые rule anomalies не labels. Physical faults не равны
  cyberattacks. Для доверенного обучения нужны реальные baselines и независимая
  разметка, новая validation/test методика и новые неподсмотренные holdouts.

Открытые технические ограничения:

- ML feed bounded100000. Retained markers сами не удаляются после оценки: для
  длительных runs надо планировать capacity/explicit prune. Иначе overflow_skipped
  растёт, primary delivery продолжается, ML coverage теряется явно. Это не lossless.
- Migration backfill только retained outbox до100000; старый relay нужно остановить
  на cutover. Полная старая Mongo history не покрыта автоматически.
- Late history может дать warmup/skip при первом snapshot; terminal score/skip
  того же model version не пересчитывается. Mongo TTL/source expiry →retry/dead;
  reset/requeue dead ML пока требует review/manual DB/backfill процедуры.
- One expected interval per model, finite window3..256; silence-gap timer отсутствует.
  Cold devices →unknown_device, invalid clock/order →unscored; online retraining нет.
- Joblib требует trusted local root; hash не подпись. Strict dependency versions,
  model64MiB/manifest1MiB limits. Shared PG role не разделяет capabilities ML/management.
- CPU1/768MiB и scalar bounded Mongo/PG calls не доказывают1000msg/s; admission
  lock не менялась. Aggregates/history queries и data export index требуют отдельного
  performance исследования. GPU/ARM64/HA/soak/production deployment не проверены.

См. ML_INFERENCE.md, ML_EVALUATION.md и reports/STAGE6.md. ML не управляет crypto.

---

## Историческое состояние этапов 0–5

# Актуальные проблемы после этапа 5

Ниже прежний аудит сохранён как исторический снимок; текущие изменения имеют
приоритет. Фактические команды/сбои/повторные запуски — reports/stage5-*.txt.

## Устранено в этапе 5

- Нет постоянной истории датчиков: verified telemetry теперь идёт через PG outbox
  в authenticated MongoDB; Sensor_Data сохранена. `src/ingestion.py`, `src/outbox.py`,
  `src/outbox_relay.py`, `src/mongo_repository.py`.
- Потеря при Mongo outage / crash до PG ACK: durable claim/retry, unique identity,
  сравнение duplicate и fencing. Dead видимы и не очищаются молча.
- create_all без миграций: src/migrate.py + migrations/0001..0003, проверки empty /
  legacy / повтор / несовместимость. Данные и replay не удаляются.
- Только файловый реестр identity: telemetry_devices содержит несекретные PG
  bindings; keys остаются scoped файлами. Disabled/mismatch блокирует admission.
- Нет авторизованной Mongo истории: /api/telemetry/history и /telemetry с прежними
  ролями, ограничением ответа, UTC/date/device filters и общим503.

## Оставшиеся ограничения

- Конечные PG/брокерные очереди, диски и retry budget: не lossless/exactly-once.
  Dead требует явного вмешательства. Без OUTBOX_RETENTION_DAYS доставленные
  payload остаются в PG; Mongo TTL также по умолчанию отключён (OUTBOX.md).
- Admission advisory lock + count backlog и один PG callback ограничивают скорость;
  1000 msg/s и 10000 устройств не измерялись. Нет генератора тысяч MQTT клиентов.
- Mongo standalone без replica set/HA; Mongo/PG TLS внутри Compose не настроен.
  Локальные runtime PG credentials пока общие с мигратором, не production RBAC.
- JSON key registry, PG binding и broker ACL согласуются явным provisioning.
  Автоматической ротации/защищённых команд нет; утеря состояния требует новой эпохи.
- Full legacy FK audit/коррекция составных PK/CRUD CREATE остаются отдельно.
  Неизвестные несовместимые схемы миграция безопасно отвергает.
- Mongo schema/index updates после первого init требуют явной admin миграции;
  автоматизированной системы Mongo schema migrations пока нет. TTL — явная команда.
- History offset-pagination не snapshot; при вставках/TTL страницы могут смещаться.
  Права sensor_data общие на устройства, tenant/device user ACL ещё нет.
- Flask dev server/local HTTP, один Socket.IO процесс, память live50 общая для
  устройств; live не подтверждает PG/Mongo commit и не гарантирует доставку браузеру.
- Минутные агрегаты metrics не очищаются автоматически; admin Mongo count может
  стать дорогим (timeout2s). Нет внешнего monitoring/alerts/CI.
- ML, FastAPI, Policy Engine, «Магма»/CRISP не реализовывались.

## Не проверено

ARM64/Raspberry Pi execution, большая нагрузка/длительный soak, crash всего хоста
с power loss, репликационные сбои, production HTTPS/TLS БД, внешний security audit
и полная нормативная проверка Ascon. Успех локальных тестов их не подтверждает.
Полный 30-дневный TTL lifecycle не воспроизводился; default удаления нет.

---

## Исторический аудит этапов 0–4

# Известные проблемы

## Актуальное состояние после этапа 4

**Устранено и проверено:**

- S03/S06: Socket.IO требует login/CSRF и same-origin, отправка только проверенным
  sid; MQTT использует TLS, password_file и минимальные ACL ролей.
- S04/S08/S09/S10: DOM XSS закрыт DOM/textContent/value, локальный safe next,
  явные поля/типы API, CSRF на изменяющих HTTP запросах, POST logout.
- S07/S11: строго валидируемый v2, bound device/topic/key/active epoch, постоянный
  sender sequence и атомарный PostgreSQL replay-state вместе с событием.
- F03/F14: API использует Session.get и generic ошибки, tag failures не выводят
  данные/traceback; browser/server не дампят decrypted payload.
- F15: stub генератора больше не заявляет ложное создание данных; POST/admin/CSRF,
  явный 501 до реализации настоящего генератора.
- Неизвестная роль fail closed. Первичные ключи и служебные атрибуты нельзя
  изменить массовым setattr. Диагностический endpoint ограничен admin.

**Оставшиеся ограничения:**

- F04/F05/F06: полная запись датчиков и CREATE API не реализованы; scalar API не
  поддерживает составные PK и теперь явно отклоняет их вместо небезопасной догадки.
- F12/F16: last 50 точек в памяти одного web-процесса; нет outbox, межпроцессного
  fanout, FK/Alembic переработки. Crash после web replay commit до emit теряет UI
  событие. Для БД-аномалий replay update и INSERT атомарны.
- F17–F19: legacy дефекты нулевых значений/индикатора и неактивного dashboard.js
  не объявляются устранёнными. table_edit2 теперь наследует защищённый шаблон.
- S12/C01/C02: wrapper валидирует входы без assert, но pure Python reference Ascon
  не объявляется constant-time или полностью независимо проверенным по стандарту.
  Есть 4 внешних KAT и boundary/tamper tests. Nonce случайный; управление ротацией
  ключей/provisioning ручные. Потеря/откат state требует новой эпохи/ключа.
- Локальная CA на 30 дней, Flask dev HTTP только loopback. Внешний HTTPS deployment,
  CA lifecycle, login rate limiting и внешний security audit не реализованы.
- ML, Policy Engine, «Магма»/CRISP и защищённые команды — будущие этапы.

**Не проверено:** реальная Raspberry Pi/ARM64, production HTTPS/reverse proxy,
нагрузка, длительные сетевые отказы/lossless delivery, disaster recovery после
потери БД/state, автоматическая ротация. Нет заявлений о полной криптостойкости.

**Доказательства:** 177 pytest passed без отключения CSRF; реальные TLS/ACL,
MQTT/PG/restart и HTTP/Socket.IO проверки; Chromium с 4 XSS payload.
[Протоколы](reports/README.md) содержат и неуспешные CSRF fixture прогоны, и их
исправление. Начальные промежуточные предупреждения/ошибки не скрыты.

## Исторический аудит исходного состояния

> Таблицы ниже — аудит безопасной базы этапа 1; номера строк исторические.
> Исправления этапа 2 перечислены в конце документа.

Дата: 2026-11-08. Номера строк относятся к безопасной базе `c352d81`.
«Статически» означает вывод из исходников, без запуска сервиса. Оценка приоритета:
P0 — блокирует безопасный запуск/корректность, P1 — следующая очередь,
P2 — качество/поддержка. Это не результаты полноценного penetration test.

## Безопасность и целостность

| ID / приоритет | Место | Факт и последствия | Проверка / состояние |
|---|---|---|---|
| S01 / P0 | `web/config.py`; `publisher/mqtt_pub.py:24`; `brocker/mqtt_brocker.py:14–18`; `web/app.py:create_default_users` | В оригинале встроены общий ключ, реквизиты БД, fallback Flask secret, пароли начальных пользователей; пароль печатался в stdout; копии в ZIP | Удалены из отслеживаемых файлов на этапе 0, оригиналы приватно сохранены. Реальная активность секретов неизвестна; при использовании в живой среде нужна их замена владельцем |
| S02 / P0 | `brocker/mqtt_brocker.py:on_message`, строки 64, 74 | device_id из AAD вставляется в SQL f-string/LIKE; нет параметризации | Статически: возможность SQL injection для отправителя, способного сформировать валидный пакет с общим ключом; общий ключ не разграничивает устройства |
| S03 / P0 | `web/app.py:34,255`; отсутствует Socket.IO connect handler | CORS `*`, нет проверки login на Socket.IO connect, emit всем клиентам | Статически: HTTP login_required не защищает канал событий; доступ/утечку подтвердить интеграционным тестом |
| S04 / P0 | `web/templates/table_edit.html:218–229,289–325,404–413` | Значения из БД вставляются в innerHTML и HTML-атрибуты без экранирования | Статически: потенциальный stored DOM XSS; Jinja tojson для передачи record не устраняет последующую небезопасную HTML-интерполяцию |
| S05 / P0 | `web/app.py:602` | debug=True, bind 0.0.0.0, dev server | Не запускался; нельзя считать production-конфигурацией |
| S06 / P1 | `publisher/mqtt_pub.py:102–109`; `brocker/mqtt_brocker.py:103–106`; `web/config.py:9–13`; `web/app.py:create_mqtt_client` | TCP/1883, TLS не настраивается; publisher/receiver без auth, web username пуст | Статически; MQTT_TLS_ENABLED не используется для tls_set; AEAD не защищает доступность/все транспортные метаданные |
| S07 / P0 | `publisher/mqtt_pub.py:57–62`; оба MQTT обработчика | Нет sequence/session/key ID, хранилища replay и дедупликации; timestamp не валидируется как replay guard | Статически; повтор одного ciphertext принят примитивом в локальной проверке. Проверка receiver как сервиса не выполнялась |
| S08 / P1 | `web/app.py:342–343` | next из query передаётся прямо в redirect | Статически: open redirect после входа |
| S09 / P1 | `web/app.py:update_record`, 470–475 | setattr для любого имеющегося атрибута, нет allowlist/типизированной схемы, допускаются PK | Статически: mass assignment/изменение ключей, потенциальное нарушение целостности |
| S10 / P1 | `web/app.py:update_record/delete_record/logout`; `web/forms.py` | Формы используют FlaskForm CSRF; общего CSRFProtect и токенов fetch нет, logout GET меняет сессию | Статически: API не имеет явной CSRF-защиты; конкретные сценарии зависят от cookie/content-type и требуют теста |
| S11 / P1 | `brocker/mqtt_brocker.py:39–57`; `web/app.py:decrypt_ascon_data` | AAD JSON разбирается до проверки тега, нет лимита пакета/строгого base64/типов/связи topic-device; algorithm берётся из пакета | Статически: ошибочные/дорогие входы, нет договорённого crypto profile. Текущий примитив допускает только один AEAD вариант; фактический downgrade на другой алгоритм не доказан |
| S12 / P1 | `web/ascon/ascon.py:188–189,214–226` | Проверки assert исчезают при `python -O`; сравнение тега обычным `==` | Статически: не полагаться на эту валидацию как на границу протокола; constant-time не подтверждено |
| S13 / P1 | `web/config.py:5,18,22`; `web/app.py:565–568` | После санации обязательны env; ключ hex без явной проверки длины; все bootstrap пароли читаются даже при наличии пользователей | Намеренная минимальная санация; удобство/валидация и безопасная инициализация остаются для следующего этапа |

## Запуск и функциональность

| ID / приоритет | Место | Факт и последствия | Проверка / состояние |
|---|---|---|---|
| F01 / P0 | `publisher/mqtt_pub.py:9`; `brocker/mqtt_brocker.py:7` | publisher требует pyascon.ascon, которого нет; receiver требует ascon.ascon вне собственного каталога; web разрешает vendored namespace только при подходящем sys.path | Проверка find_spec из корня: pyascon/ascon не найдены; сборки Python-пакета нет |
| F02 / P0 | `web/requirements.txt`; requirements других модулей отсутствуют | Paho не зафиксирован, NumPy/ML/pyascon/email-validator не описаны полностью; publisher требует CallbackAPIVersion.VERSION1 (API Paho 2.x), остальные используют старую форму | В текущем окружении web/MQTT/ML пакеты отсутствуют; совместимость зафиксированных версий с Python 3.14 не проверена |
| F03 / P0 | `web/app.py:479,484,512,514,525` | db_logger/error_logger/json_audit_logger нигде не определены. Ошибка возникает после commit, затем error_logger вызывает следующую ошибку | Статически подтверждено отсутствием определений: возможны изменённая БД и HTTP 500; rollback уже не отменит commit |
| F04 / P0 | `web/app.py:111,217–235,551` | Вызовы save_sensor_data закомментированы; функция создаёт SensorData без session.add и commit | Статически: рабочей записи телеметрии этой цепочкой нет; сообщение об успешном сохранении недостоверно |
| F05 / P0 | `web/templates/table_edit.html:360–372`; `web/app.py:routes` | UI отправляет POST /api/<table>, но соответствующего маршрута нет | Статически: CREATE недоступен, несмотря на ролевой флаг и кнопку |
| F06 / P0 | `web/models.py:150–154,168–172,257–258`; `web/app.py:460–465,500–504`; `table_edit.html:364–366,423–425` | Parameters/DeviceConfiguration/GlobalReport имеют составные PK, API/UI используют один scalar ID | Статически: generic update/delete не поддерживает эти таблицы |
| F07 / P1 | `brocker/mqtt_brocker.py:70,80` | Для datetime используются %d в pymssql INSERT | Вероятная ошибка преобразования параметров; драйвером/сервером не проверено |
| F08 / P0 | `brocker/mqtt_brocker.py:27–34,65,99,102` | После ошибки connect conn=None; cursor/rollback без guard; один глобальный conn без восстановления/закрытия курсоров | Статически: вторичное исключение в обработчике, нет устойчивости БД |
| F09 / P1 | `brocker/mqtt_brocker.py:48–51,63–81` | Локальные naive timestamp, поправка +3ч, metadata default unknown парсится как дата; отсутствующие датчики сравниваются с числами; elif теряет вторую причину аномалии | Статически: ложные задержки/TypeError/неполная диагностика; синхронизация часов не учитывается |
| F10 / P1 | `web/app.py:23` | FileHandler('/var/log/flask_mqtt.log') создаётся при импорте | Вероятная ошибка прав для обычного пользователя/контейнера; Flask import не запускался из-за отсутствующих зависимостей |
| F11 / P1 | `publisher/mqtt_pub.py:102–163`; `brocker/mqtt_brocker.py:102–107`; `web/app.py:587–594` | Publisher/receiver соединяются при импорте, web запускает MQTT только в main | Статически: сложность тестирования; WSGI import не запускает web MQTT; отсутствие graceful shutdown у receiver |
| F12 / P1 | `web/app.py:47–51,244–259` | Буфер общий для всех устройств, без device_id и разделения процессов; web отбрасывает метаданные AAD | Статически: смешение потоков, неполная история после рестарта, гонки при нескольких обработчиках; нагрузкой не проверено |
| F13 / P1 | `publisher/mqtt_pub.py:143`; `brocker/mqtt_brocker.py:24`; `web/app.py:78` | Результат publish не проверяется, wait_for_publish нет; подписки с QoS 0 | Статически: нет end-to-end гарантии доставки/персистентности, QoS 1 сам по себе этого не обеспечивает |
| F14 / P1 | `web/app.py:201,206` | plaintext None вызывает decode exception, ловится общим except; ValueError печатает буквальное {e} | Статически: неясная диагностика tag failure, исключения используются вместо явной проверки |
| F15 / P1 | `web/app.py:529–559` | Тестовые данные не сохраняются, но ответ заявляет создание count записей | Статически: ложный успех, endpoint не ограничен ролью администратора |
| F16 / P2 | `web/models.py:107–297` | Нет ForeignKey, relationship, миграций; nullability/составные ключи требуют сверки с реальным MSSQL | Только ORM исследована; состояние реальной БД неизвестно |
| F17 / P2 | `web/app.py:413`; `models.py:295–296`; `web/app.py:279–280` | query.all без пагинации; schema columns из первой записи; 0 в сериализации SensorData становится None | Статически: пустая таблица не даёт полей создания, нули теряются, возможны большие ответы |
| F18 / P2 | `web/templates/base.html:36`; `dashboard.html:301–304,332` | role хранится строкой, выводится через .name; нулевые значения показываются как '--'; updateStatus не вызывается | Статически: неверное отображение роли/измерений, ложный online |
| F19 / P2 | `web/static/js/dashboard.js:45–75,91–96`; `templates/dashboard.html:109–349` | Две реализации dashboard, static JS не подключён. В нём массивы chartData переназначаются после создания графиков без переназначения chart.data | Статически: дефект неактивной реализации; активный inline вариант это обходит |
| F20 / P2 | `web/templates/table_edit2.html:65–105`; `table_edit.html:200` | Неиспользуемый шаблон ссылается на отсутствующие modal DOM; CSS icons подключён как script в активном шаблоне, затем также как link | Статически: неполный альтернативный интерфейс и некорректный ресурс |
| F21 / P1 | `publisher/mqtt_pub.py:33`; `web/ascon/ascon.py:187–188`; `web/ascon/writer.py:8` | Legacy default Ascon-128 не поддерживается; writer импортирует typing.override | Неподдерживаемый default подтверждён локальным AssertionError; writer требует Python 3.12+, на 3.14 импорт успешен |

## ML и криптографические доказательства

| ID / приоритет | Место | Факт / ограничение |
|---|---|---|
| M01 / P0 для интеграции | `classifier/iot-test.ipynb`, ячейки 1–7 | Датасета нет; Kaggle-путь, сетевые flow-признаки не равны двум датчикам MQTT. Схема feature extraction из реального канала отсутствует |
| M02 / P1 | notebook, ячейки 6–8,11 | get_dummies до split, массив без имён колонок; preprocessing/encoder не сохраняются. Риск несовпадения inference и утечки оценки требует нового эксперимента |
| M03 / P1 | notebook, ячейки 7–12 | Только случайный split и одна seed; нет проверки по устройствам/сессиям/времени, отдельного validation и доверительных интервалов; прежние метрики не воспроизведены |
| M04 / P0 для интеграции | notebook, joblib.dump в ячейках 8,11 | Нет .pkl, joblib.load, versioned pipeline и online inference; сервисы моделей не используют |
| C01 / P0 для заявления соответствия | `web/ascon/README.md`, `ascon.py`, `genkat.py:42–48` | README ссылается на draft, независимые KAT отсутствуют. Round trip одной реализации не подтверждает соответствие финальному NIST SP 800-232 |
| C02 / P1 | `publisher/mqtt_pub.py:28–30`; три конфигурации ключа | os.urandom не даёт абсолютной гарантии уникальности nonce; нет учёта nonce/key lifetime, ключей по устройствам, rotation и provisioning |
| C03 / P0 для целевой системы | всё дерево | Policy Engine, minimum security floor, hysteresis, signed/authenticated commands, anti-replay, «Магма» и проверка CRISP отсутствуют. Декларации Algorithm/Parameters в БД не реализуют эти механизмы |

## Границы аудита

Нет доступного ARM64 устройства, установленного приложения, брокера, датасета и
предоставленной MSSQL БД. Зависимости не устанавливались, сетевые адреса оригинала
не использовались, функциональные web/SQL/MQTT проверки не заявляются успешными.
Проверка синтаксиса, локальные проверки Ascon и Git не заменяют эти проверки.
Унаследованные trailing whitespace/пустые строки в конце файлов дают код 2
`git diff --cached --check` для первоначального добавления; массовое форматирование
не выполнялось. Отдельных автоматических тестов и CI в исходном проекте нет.

## Исправления этапа 2 — PostgreSQL и воспроизводимый runtime

Проверено на новой PostgreSQL, без исходной MSSQL и без переноса её данных.
Подробные команды и ограничения — [RUNTIME.md](RUNTIME.md).

| ID | Текущее состояние |
|---|---|
| S02 | Закрыта в receiver: параметризованный PostgreSQL запрос, литеральный starts_with вместо сетевого SQL f-string; негативная проверка device_id проходит |
| S05 | Для module entrypoint закрыта: debug=False, loopback по умолчанию; сервер остаётся локальным dev server |
| S13 | Явная валидация hex-ключа и PostgreSQL URL; bootstrap пароли необязательны, существующие пароли сохраняются; проверено |
| F01/F02 | Единый vendored Ascon, module entrypoints, uv.lock и экспорты; импорты проверены без соединений и секретов; MSSQL зависимости удалены |
| F03 | Логгеры определены; простые PUT/DELETE на PostgreSQL возвращают успех после commit, проверено |
| F07/F08 | pymssql/сырой глобальный conn удалены; PostgreSQL engine.begin с откатом; ошибочный INSERT и последующее восстановление проверены |
| F09 | Убраны +3 часа, новые timestamp UTC; legacy naive принимается за UTC. Валидация типов и все причины одновременно остаются будущей работой |
| F10/F11 | FileHandler только при явном запуске и LOG_FILE; main guards для всех процессов, отсутствие сети на импорте проверено. WSGI по-прежнему не запускает MQTT автоматически |
| F13 | Paho VERSION2, QoS 1 подписок, wait_for_publish с timeout у publisher. Сквозной обмен/персистентность MQTT ещё не проверены |
| F14 | Явная проверка None и корректная строка ValueError; совместимость publisher/web проверена |
| F21 | Default Ascon-AEAD128 исправлен; Python 3.12.16 выбран для runtime и typing.override |
| C01 | Добавлены 4 внешних KAT ascon-c, все проходят; полное соответствие/аудит по-прежнему не утверждается |

Остаются S03/S04/S06–S12 (кроме перечисленных частичных улучшений), F04/F05/F06,
F12/F15–F20, ML-интеграция и криптографические механизмы последующих этапов.
F16: новая схема создана из неизменённых ORM-моделей, FK/Alembic ещё нет.
Два предупреждения LegacyAPIWarning для Query.get в PUT/DELETE остаются;
массовая модернизация ORM в этот этап не включена.

Первый запуск DB-тестов из песочницы дал 6 ошибок подключения. Подробный traceback
раскрыл временный пароль тестовой PostgreSQL; пароль сразу заменён, в pytest
установлен --tb=short. После предоставления доступа к loopback все 103 теста
прошли. Исходные секреты проекта не использовались; значения паролей в Git не
добавлялись. Временная БД остановлена после проверок.

## Обновление этапа 3

F13: реальный QoS 1 обмен через Mosquitto и восстановление после рестарта broker
проверены. Это не доказывает lossless delivery, дедупликацию или anti-replay.
Receiver выставляет readiness только после успешного SUBACK и сбрасывает при
разрыве. Брокер в Compose работает anonymous/без TLS, опубликован на loopback;
S06 и другие оставшиеся проблемы безопасности относятся к этапу 4.

Демонстрационные записи отделены opt-in профилем, idempotency/conflict rollback
проверены. Начальные ошибочные Docker-образы с ZIP/.git удалены адресно; контекст
и COPY исправлены, новый образ проверен. Smoke Tag_Name укорочен под существующий
лимит 30. Полные результаты/ошибки приведены в DEVELOPMENT_STATUS.md.

## Этап 7.5b — устранённое и оставшиеся ограничения

Устранено: отсутствовал изолированный TLS research collector/generator;
не было verified connection-level смешанной разметки/unknown. Созданы lab,
GT/builder/validator/watchdogs, no zero-fill, persistent counters, source hashes.
Startup provisioning обязателен: первый неудачный пилот отдельно сохранён.
Исправлены laboratory password/topic length shortcuts;10captures исключены
явной hash-bound курацией до обучения, raw data не удалялись. Syntax error
промежуточного447dec0 исправленe9d3241; проверки текущего кода успешны.

Остаётся: crypto/ML/Policy контура приложение не менялись, Network IDS online
по-прежнему отсутствует. Labels — controlled connection activity, не доказанная
вредоносность каждого пакета. Unknown27.044%, один negative time_delta capture
вquarantine.76normalQoS1DUP не означают атаку; Policy baseline replay semantics
этим исследованием не переопределялись.

59groups и strict split прошли, но statistical independence/real-world detection
не доказаны; duplicate purge удаляет68.2%known rows и меняет prevalence. Последняя
часть имеет только5positive capture groups/60violation rows. Post-fix batch,
короткие auth/ACL sessions, общий host/kernel/software могут давать shortcuts.
Нужны held-out host/device/scenario и отдельный совместимый внешний набор.
Новые RF/IF не обучены, scientific final/external scores отсутствуют.

Не проверено: ARM, IPv6, абсолютная clock/label accuracy, peak tshark RSS,
реальные атаки/physical IoT baseline, live ML одновременно с collector fault в
одном collecting project. Отдельный real ML recovery regression проходит.
CPU/RAM hard quotas есть; disk limits — watchdog budgets с допустимым polling
overshoot, не filesystem hard quota. Для жёсткой изоляции предпочтителен VM/host.
Ни Packet PCAP, ни traces с анонимным отказом не подтверждают spoofed device ID.

Внешний аудит7.5b: MQTT_UAD не хватает4passive fields; MQTTEEB-D raw/header/group
audit не выполнен; IoT-SFC log granularity требует отдельного контракта и проверки
лицензии конкретной версии. Источники не скачаны целиком/не смешаны с own lab.
Доказательства и команды — docs/RESEARCH_75B_RESULTS.md и reports/stage75b-*.

## 7.5b-fix — уточнение достоверности данных

Реально воспроизведено: старый validator принимал logical label tamper с новыми
hashes. Исправлено independent per-row oracle +bounded PCAP identity audit.
Packet_audited на старом connection-level наборе было неверным термином; архив
не переписан, новая версия2.2 connection/window. Rate/pattern больше не основаны
на двух actions; ACL привязан к session/time, replay к timed PG identity и
независимому digest witness. Anonymous AEAD tamper actor остаётся unknown.

Исправлены реальные broker parser omissions: reconnect close сendpoint и
CONNACK5 при параллельном pending health connection. Session lifecycle теперь
ограничивает local times; Nonfinite/duplicate-key journals отвергаются.
Новые source outage/collector faults и coherent-hash tamper проверены реально.

Остаётся: у старых59captures нет нужных независимых доказательств, поэтому в новой
archive версии33848known→unknown, итого46395unknown, training-ready groups0.
Новый real probe2269rows (1509normal/190controlled/570unknown),9captures/5positive
capture groups — мало для split. Старый holdout не содержит positive replay и
pattern_change; validation не содержит bad_credentials/bounded_rate после purge.
Одинаковый5-vector не физический дубликат. Captures disjoint, но paired seeds
пересекаются7/9/2 — зависимость условий остаётся риском. Старый split не заменён.

Независимый software oracle и три trusted lab sources не внешний gold standard.
Label accuracy/clock accuracy/real attack realism/transfer не измерены; новые
RF/IF не обучены. Source journals не подписаны, local operator/shared writable
research volume — граница доверия, не tamper-proof recorder. Observer keyless,
но использует существующую readonly web-role своего lab broker. Disk watchdog
не hard quota. Все эти ограничения обязательны для дипломной интерпретации.
Подробный итог/фактические commands/exit codes: RESEARCH_75B_FIX_RESULTS.md.

## Stage11 limitations

- Новый MGM provider пригоден только для явно разрешённого software lab. Whole-AEAD constant-time и независимый audit не подтверждены: MGM multiplication содержит secret-dependent branch; upstream CT Kuznyechik experimental.
- One-shot Go process на операцию добавляет spawn/key-schedule overhead; не экстраполировать результаты на native persistent provider/ARM.
- Python/Go GC не гарантирует zeroization всех копий ключей.
- Budget намеренно расходуется на все committed grants MGM-key устройства, даже пока работает Ascon/AES; неиспользованный хвост сгорает. Rotation/recovery не выполняются silent reset.
- Joint PG+SQLite rollback без внешнего monotonic anchor не обнаруживается; нужны новые ключи/эпоха после reviewed restore.
- Magma-MGM остаётся непроверенным design-кандидатом, недоступна в UI/live pipeline.
- Mongo schema upgrade явный; отсутствие нового enum даёт delivery error/backlog, не разрешение отключить validator.

## Stage12 confirmed limitations

- Whole-provider constant-time is unverified: compiled MGM GF multiplication includes a secret-dependent branch. No remote key-recovery exploit demonstrated; IPC optimization does not remove this. Kuznyechik lab-only remains.
- Persistent worker increases possible key residency; no key cache, bounded lifetime and best-effort clear do not guarantee GC zeroization. GOMEMLIMIT is soft within service hard limits. No network crypto endpoint.
- PyGOST5.12 raw size/empty-input API findings reproduced; strict wrapper is research-only. Official5.13 archive was not TLS-verifiable here; its behavior remains unverified.
- Magma64-bit budget with aggregate authentication attempts is too short for current lease/rekey lifecycle. No live activation. Safe key rotation and versioned short grants are design only.
- Immutable-original and updated one-shot measurements differ across batches; cause not established. CPU/frequency/scheduler isolation, clock accuracy, ARM/hardware and production certification are not claimed.
- Early raw outputs do not all embed top-level source SHA/argv; original files retained, hash/source-context inventory and recorded nested argv supplied. No retroactive invented provenance.

Fixed adapter availability bugs: stale executable-path cache and stderr-EOF/complete-stdout race, both covered by behavioral regressions. [Details and actual evidence](STAGE12_RESULTS.md).

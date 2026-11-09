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

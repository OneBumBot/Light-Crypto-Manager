# Состояние разработки и план

Дата: 2026-11-08. Выполнены этапы 0–3. По команде пользователя PostgreSQL
заменила MSSQL уже в этапе 2; переноса данных недоступной MSSQL нет.
Этап 4 не начат. Push и merge в main не выполнялись.

## Сохранённые этапы

| Этап | Результат | Git |
|---|---|---|
| 0 — безопасная исходная версия | Корневой Git/main, исключения, приватная копия оригинала, санация конфигурации и notebook outputs | `908dd56` — `chore: establish safe legacy project baseline` |
| 0 — сохранение прав файлов | Права исполнения трёх vendored Python-скриптов сохранены отдельным коммитом без переписывания истории | `c352d81` — `chore: preserve executable modes of vendored Ascon scripts` |
| 1 — инвентаризация | Файлы, существующая архитектура, проблемы, статусы и план | `feature/component-inventory`, `76ca884` |
| 2 — воспроизводимый runtime / PostgreSQL | Python/lock, module entrypoints, PostgreSQL вместо MSSQL, проверки | `feature/reproducible-postgres-runtime`, `fca2153` |
| 3 — Compose/Mosquitto | Локальные сервисы, healthchecks, demo и реальный MQTT/DB smoke | `feature/local-mqtt-compose`, коммит `build: add local Mosquitto and component compose services` |

Точный хеш последнего коммита см. `git log -1` и итоговый отчёт. Хеш не
вписывается в содержимое самого коммита. В main осталась безопасная база;
ветка инвентаризации сохранена отдельно, этап 3 основан на коммите этапа 2.

## Статусы компонентов

«Существует» подтверждает наличие файлов, «частично реализовано» — неполный
сценарий, «не проверено» — нет достаточного запуска, «проверено тестами» имеет
ровно указанную область проверки и не распространяется на весь сервис.

| Компонент / возможность | Статус | Доказательство / предел |
|---|---|---|
| Корневой Git и безопасная база | существует | Два коммита в main, приватный оригинал с manifest, чистое состояние после этапа 0 |
| Publisher | проверено тестами | Реальный процесс demo отправляет MQTT через Mosquitto; пакет наблюдён и расшифрован. ARM64 не запускался |
| Запуск publisher на Raspberry Pi OS/ARM64 | не проверено | Dry-run готовых runtime wheels для ARM64/CPython 3.12 успешен; на устройстве не запускался |
| Настоящий MQTT broker / Mosquitto | проверено тестами | Mosquitto 2.1.2 в Compose, QoS 1 healthcheck, loopback порт и volume |
| Receiver в brocker | частично реализовано | Аномалии пишутся через живой MQTT; SUBACK readiness и переподключение проверены. Отдельный worker, ML, persistence датчиков ещё впереди |
| Сквозной MQTT обмен | проверено тестами | Реальный publisher/Mosquitto/receiver/PostgreSQL; повреждённые пакеты не ломают цикл; повторно после рестарта broker |
| Notebook экспериментов | существует | 13 ячеек RF/IF, исторические метрики просмотрены, не воспроизведены |
| Датасет, готовые модели и preprocessing artifacts | отсутствует | Есть только код загрузки CSV и joblib.dump |
| Online ML / согласованные признаки | отсутствует | Сетевые признаки отличаются от temperature/humidity |
| Flask, формы и роли | частично реализовано | Запуск и вход на PostgreSQL проверены; полный аудит ролей/socket впереди |
| ORM предметной области | проверено тестами | 14 таблиц созданы на PostgreSQL из неизменённых моделей; составные PK/FK/migrations ещё требуют работы |
| CRUD | частично реализовано | Простой PUT/DELETE проверен на PostgreSQL; POST/составные PK пока не реализованы |
| Сохранение телеметрии | частично реализовано | save_sensor_data отключена и не завершает транзакцию |
| Шаблоны, CSS, JS, realtime UI | частично реализовано | Макеты/графики/Socket.IO есть; браузер не запускался, обнаружены дефекты |
| Работа Flask/API/PostgreSQL | проверено тестами | Вход, dashboard render, история, простой PUT/DELETE; живой HTTP /login=200. Остальные пути полностью не покрыты |
| Локальный примитив Ascon-AEAD128 | проверено тестами | 81 PT/AAD случай: round trip, длина, отказы при изменении tag/AAD/key/nonce |
| Соответствие Ascon финальному SP 800-232 | не проверено | 4 внешних KAT ascon-c проходят; полной нормативной проверки/аудита нет |
| genkat/writer | существует | Импорты на Python 3.14.9 успешны, полный генератор не запускался |
| Синтаксис Python и notebook | проверено тестами | compile() успешен для 9 .py и 13 кодовых ячеек; без исполнения приложений |
| FastAPI / Alembic | отсутствует | PostgreSQL перенесена в этап 2; API и миграции остаются последующими этапами |
| Отдельный оформленный MQTT worker | частично реализовано | Receiver теперь отдельный Compose-сервис; выделение общего ingestion-кода, полная запись датчиков и жизненный цикл worker остаются этапом 5 |
| Policy Engine / профили / anti-replay / защищённые команды | отсутствует | Алгоритмические справочники БД не являются движком политики |
| «Магма» / проверенный профиль CRISP | отсутствует | Нет реализации или подтверждения требований |
| Автоматические тесты | проверено тестами | 108 passed в Docker, 10 DB-тестов; 2 прежних Query.get предупреждения. CI ещё нет |
| Docker Compose | проверено тестами | Запуск с healthchecks, init-db, demo/web profiles, smoke и tests; volumes тестового контура удалены после проверки |
| CI | отсутствует | Локальные тесты не заменяют CI |

## Фактические проверки этапов 0–1

Среда: Linux x86_64, Python 3.14.9. Установка зависимостей и сервисов не выполнялась.

| Проверка | Результат |
|---|---|
| Корень и вложенные .git | Исходно корневой Git отсутствовал; один вложенный Ascon master/ed24e54, сохранён |
| Git identity | user.name/user.email уже настроены, не изменялись |
| Архив и исходники до git add | Просмотрены конфигурационные присваивания, пароли, текстовые кандидаты и ZIP; секретные значения не печатались |
| Приватная копия | Каталог 0700, tar.gz и manifest 0600; хеши всех 52 исходных файлов сверены с архивом |
| Санация | Подготовленные 24 файла не содержали выделенных исходных ключей/паролей/URI; исходники всех ячеек notebook совпадают с оригиналом |
| Обычные файлы Ascon | В индексе нет mode 160000; checkout базы содержит сам код, вложенный Git не удалён |
| Синтаксис | compile() для 9 Python-файлов и 13 ячеек успешен |
| Ascon round trip | 81 сочетание длин PT/AAD; ciphertext длиной PT+16; успешно |
| Ascon отрицательные случаи | Для каждого из 81 пакета изменение tag, AAD, key и nonce → None; успешно |
| Ascon legacy default | Ascon-128 вызывает AssertionError в vendored реализации; несовместимость подтверждена |
| Повторный ciphertext | Повторная расшифровка успешна; anti-replay у примитива отсутствует по назначению, протокол его не добавляет |
| Ascon genkat/writer | Импорт успешен на текущем Python; внешний эталон/полная генерация не проверены |
| Зависимости | Web/MQTT/ML пакеты и pyascon отсутствуют по importlib.metadata/find_spec; запуск сервисов не выполнен |
| Git whitespace этапа 0 | Неуспешно, exit 2: 275 унаследованных замечаний к пробелам/EOF; legacy форматирование сохранено |
| Git diff --check этапа 1 | Успешно: новые документы без замечаний |

Проверка секретов — локальный аудит известных литералов и подозрительных полей,
а не гарантия обнаружения любого секрета. Приватный архив/вложенная история не
публикуются. Никакие реальные ключи для тестов Ascon не использовались.

Пример повторения локальной проверки Ascon из корня (без сети/пакетов):

```bash
python3 -B - <<'PY'
import importlib.util
spec = importlib.util.spec_from_file_location('audit_ascon', 'src/web/ascon/ascon.py')
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)
key = nonce = bytes(range(16))  # только публичные тестовые данные
lengths = [0, 1, 7, 8, 15, 16, 17, 31, 32]
for plen in lengths:
    for alen in lengths:
        pt, ad = bytes(range(plen)), bytes(range(alen))
        ct = a.ascon_encrypt(key, nonce, ad, pt)
        assert len(ct) == plen + 16
        assert a.ascon_decrypt(key, nonce, ad, ct) == pt
        changed_tag = ct[:-1] + bytes([ct[-1] ^ 1])
        changed_key = bytes([key[0] ^ 1]) + key[1:]
        changed_nonce = bytes([nonce[0] ^ 1]) + nonce[1:]
        assert a.ascon_decrypt(key, nonce, ad, changed_tag) is None
        assert a.ascon_decrypt(key, nonce, ad + b'x', ct) is None
        assert a.ascon_decrypt(changed_key, nonce, ad, ct) is None
        assert a.ascon_decrypt(key, changed_nonce, ad, ct) is None
print('PASS: 81 round trips and four tamper checks per case')
PY
```

Это проверка одной реализации на тестовых данных с фиксированными key/nonce,
а не шаблон безопасного применения nonce в реальной системе.

## Фактические результаты этапа 2

Подробные команды установки, запуска, инициализации PostgreSQL и тестов:
[RUNTIME.md](RUNTIME.md). PostgreSQL перенесена в текущий этап по явной команде
пользователя; выделение worker, FK/Alembic и полная запись телеметрии не выполнены.

| Проверка | Результат |
|---|---|
| Окружение | CPython 3.12.16, uv 0.13.6; uv.lock разрешает 137 пакетов, все runtime/ML группы установлены локально |
| Изолированные проверки | 95 passed без БД; импорт всех трёх модулей без env/подключений/FileHandler, key/config validation, Flask login page, publisher → web AEAD |
| Ascon | 4 внешних фиксированных KAT ascon-c + 81 набор PT/AAD с tamper checks; успешно. Исходники Ascon не менялись |
| PostgreSQL | Временный postgres:17-alpine, image digest `sha256:3540c0362c809df084ffac0ae69fe794515f9de92692f02178bcdce0ef0302ac`; только случайный loopback-порт |
| Схема и CLI | 14 таблиц, init-db повторяем, bootstrap только по явным паролям, существующие пароли сохраняются |
| Web/PostgreSQL | Вход, dashboard render, чтение явно записанной тестовой истории, простой PUT/DELETE успешны |
| Receiver/PostgreSQL | Обе причины аномалий и normal case; отвергаются подмена тега и device_id с SQL-синтаксисом; ошибка INSERT откатывается и следующая обработка успешна |
| Итог pytest | **103 passed, 2 LegacyAPIWarning (Query.get)**; 8 тестов используют PostgreSQL, схемы изолированы и удаляются |
| Живой процесс web | init-db CLI успешен, serve без MQTT, /login=200 по HTTP, LOG_FILE работает; процесс остановлен |
| ML | 13 ячеек синтаксически корректны; исходные импорты успешны с pandas 2.3.3 / scikit-learn 1.9.1; обучения/датасета нет |
| ARM64 | uv pip dry-run --only-binary для CPython 3.12/aarch64-manylinux_2_28: 28 runtime пакетов разрешены. Реального ARM64 запуска нет |
| Статика | compileall, Ruff выбранных fatal/undefined проверок, uv lock --check, git diff --check успешны |
| Секреты и сохранность | Локальные env/логи/venv/cache исключены, исходные секретные литералы не возвращены; модели, шаблоны, notebook и vendored Ascon не изменены |

Первый запуск DB-тестов из sandbox: 6 ошибок соединения; после разрешения доступа
к loopback проверки успешны. Стандартный traceback включил временный пароль
изолированной БД — пароль заменён, pytest настроен на --tb=short. Реальные исходные
реквизиты не использовались. Контейнер с временной БД остановлен после проверок.
Тестовой MSSQL не было; миграция её данных не проверялась. Полный MQTT обмен,
браузерные сценарии, обучение ML и реальное ARM64 выполнение не заявляются.

## Фактические результаты этапа 3

Инструкции: [COMPOSE.md](COMPOSE.md). Реализован только локальный контур и проверки;
web/ORM/ML/криптографический исходник не переписывались. В receiver добавлены
сброс/установка readiness marker по disconnect/положительному SUBACK.

| Проверка | Результат |
|---|---|
| Git перед этапом | Чистая ветка этапа 2, HEAD fca2153; создана feature/local-mqtt-compose |
| Compose config | С приватным сгенерированным env config --quiet успешен; с пустыми секретами пример конфигурации ожидаемо отклонён |
| Build | Python 3.12.16, Mosquitto 2.1.2, PostgreSQL 17.11; образы закреплены digest. Classic builder успешно работает, несмотря на предупреждение об отсутствии buildx |
| Инициализация | PostgreSQL healthy → init-db exit 0; явный demo-setup exit 0; receiver ready только после SUBACK; web /login healthy |
| MQTT/DB smoke | Два валидных AEAD сообщения → ровно две аномалии своего временного устройства; JSON/tag corruption отвергнуты, следующий пакет принят; fixture очищена |
| Реальный publisher | Процесс demo наблюдён через broker; packet успешно расшифрован, данные temperature/humidity присутствуют |
| Broker restart | Receiver получил новый SUBACK; повторный полный smoke и наблюдение demo publisher успешны |
| Порты | У broker/web публикация только 127.0.0.1, у PostgreSQL нет host binding; для аудита использованы случайные порты |
| Образ приложения | UID/GID 10001, приватные env, legacy ZIP, Git, кеши и notebook отсутствуют в итоговом образе |
| Изолированные тесты | 98 passed, 10 DB-тестов deselected при отдельном запуске без PostgreSQL |
| Полный pytest в Compose | **108 passed, 2 LegacyAPIWarning** для прежнего Query.get. Включены rollback/idempotency/conflict тесты demo seed и SUBACK/config protection |
| Статика | Ruff выбранных правил, compile, git diff --check; экспорты зависимостей и uv.lock согласованы |
| Сохранность | Существующие web/publisher/ORM/templates/ML/Ascon не менялись; реальные секреты исключены из Git; тестовый Compose остановлен, удалены только volumes проекта lcm-stage3 |

Ошибки первого прогона не скрываются: smoke сначала получил DataError, поскольку
его случайный Tag_Name был длиннее 30 символов. Исправлен до 26 символов.
Проверка первого локального образа также обнаружила ZIP/вложенную .git из-за
семантики исключений Docker-контекста. Образы и их промежуточные копии удалены
адресно, без global prune; Dockerfile переключён на явное копирование файлов,
контекст исправлен, новый образ прошёл проверку. Ошибочные образы не публиковались.
Реальные значения исходных секретов не выводились и в Git не возвращались.

Ограничения: anonymous MQTT без TLS/ACL только в локальном dev контуре; остаются
известные проблемы web, нет anti-replay и гарантий отсутствия потерь при сбоях.
Receiver сохраняет только аномалии, web — live данные в памяти. Browser UI/ARM64/
ML/нагрузка не проверялись. Alembic, полноценный worker и sensor persistence —
следующие этапы; этап 4 не начат.

## Технический план с учётом выполненного этапа 3

Перед каждым этапом: проверить чистый Git/сохранение предыдущего, создать отдельную
ветку от согласованной базы, менять только нужные файлы, выполнить относящиеся
проверки, обновить этот документ и сделать коммиты. Merge в main/push — только
по отдельному разрешению. Этап 1 остаётся несмешанным с реализацией.

| Этап / ветка | Конкретные коммиты | Критерий завершения |
|---|---|---|
| 2 `feature/reproducible-postgres-runtime` | `feat: establish reproducible PostgreSQL runtime` | Выполнено с изменением по команде пользователя: Python 3.12.16, uv.lock и экспорты; импорты без соединений, единый Ascon, log/env; PostgreSQL вместо MSSQL, 103 теста. ARM64 — только проверка wheels, не выполнение |
| 3 `feature/local-mqtt-compose` | `build: add local Mosquitto and component compose services` | Выполнено: конфигурация и healthchecks, demo/web profiles, временные smoke fixtures, 108 tests, реальный MQTT/DB обмен и повтор после broker restart. Только loopback, TLS/ACL впереди |
| 4 `fix/telemetry-protocol-security` | `fix: close critical legacy SQL and web vulnerabilities`; `feat: define validated versioned telemetry envelopes`; `test: cover malformed and tampered telemetry` | SQL/транзакции/логгеры исправлены в этапе 2; здесь закрытые Socket.IO события, XSS/redirect/CSRF/debug; валидируемая схема, размеры, UTC, topic/device binding, crypto allowlist. До устранения критических проблем контур не открывать внешней сети |
| 5 `feature/migrations-mqtt-worker` | `feat: add relational constraints and Alembic migrations`; `refactor: extract MQTT ingestion worker`; `test: verify transactional telemetry persistence` | Явные FK/индексы/составные ключи, seeds и миграции на чистой БД, worker lifecycle/reconnect, единая транзакция приёма, запись датчиков/аномалий, контракт истории; существующие шаблоны сохранены |
| 6 `feature/ml-inference-pipeline` | `docs: define observable ML feature contract`; `feat: export versioned preprocessing and anomaly model`; `test: reproduce anomaly evaluation` | Решение: собирать сетевые признаки либо обучать новую модель по телеметрии. Версия/хеш датасета, train-only preprocessing, split по времени/группам, сохранение schema/encoder/model/versions, воспроизводимые метрики и inference. Выход ML — score/сигнал аномалии |
| 7 `feature/adaptive-policy-engine` | `feat: enforce minimum crypto profiles and policy hysteresis`; `feat: authenticate profile commands and reject replays`; `test: verify policy transitions and command recovery` | Минимальный уровень защиты обязателен; устойчивые аномалии быстро усиливают профиль, снижение лишь после продолжительного стабильного окна; ML не выбирает алгоритм. Key/session/sequence, хранение replay-state, дедупликация, authenticated commands, подтверждение/повторы/rollback, restart tests; не ранжировать алгоритмы по названию без модели угроз |
| 8 `feature/fastapi-web-integration` | `feat: expose authenticated FastAPI telemetry and table APIs`; `refactor: connect existing templates to FastAPI`; `test: cover web roles and realtime flows` | Сохранённые шаблоны/CSS/графики; контракт авторизации и realtime, полный CRUD с составными PK, пагинация; роли/CSRF/socket/browser tests; отключение legacy Flask пути только после проверки паритета |
| 9 `feature/domestic-crypto-profile` | `docs: specify Magma profile and CRISP requirements`; `feat: implement verified domestic crypto profile`; `test: validate domestic profile vectors and interoperability` | Сначала источники требований/профиль: режим, аутентификация, key/nonce limits, anti-replay и совместимость; независимые векторы. «Магма» не объявляется полным CRISP; при неполноте требований это ограничение явно фиксируется |
| 10 `feature/system-validation` | `test: add integration security and load scenarios`; `docs: publish reproducible experiment and deployment procedures` | Полная цепочка Compose, fuzz/negative cases, перезапуски/потери/повторы, нагрузка и ARM64 замеры, фиксированные параметры экспериментов, документация ограничений и фактические результаты |

Порядок уточнён результатами аудита: согласование импортов, локальная проверка
Ascon и переход на PostgreSQL выполнены в этапе 2; безопасность legacy закрывается до внешнего доступа,
а replay/dedup полностью фиксируются до включения адаптивного управления.
Инфраструктура ограничена задачей: без Windows, SIEM и лишних сервисов.
Наличие «Магмы» само по себе не доказывает ни полноту CRISP, ни криптостойкость
всей системы; сравнение профилей требует явной модели угроз и требований.

Этап 3 завершён. Следующий шаг — этап 4: критические проблемы безопасности
и валидируемый единый формат MQTT. Работа остановлена до отдельной команды пользователя.

## Этап 4 — в работе

Создана feature/security-hardening от чистого 5be5444. Транспорт MQTT переведён
на TLS/8883 с аутентификацией и ACL, отдельными материалами ролей вне Git/образов.
Положительные/отрицательные подключения и ограничения publish/read проверены на
реальном Mosquitto. Протокол: docs/reports/stage4-transport.txt.
Anti-replay, валидация v2 и web-защита пока не завершены; этап не объявляется готовым.

Блок MQTT v2/anti-replay завершён: 146 passed (2 прежних Query.get warning),
включая конкурентное принятие 16 копий одного пакета ровно один раз, rollback
счётчика вместе с INSERT, валидацию и счётчик SQLite. Реальный TLS smoke прошёл;
после force-recreate receiver ранее сохранённый пакет отвергнут без новой записи.
Результаты: docs/reports/stage4-protocol.txt, схема: docs/MQTT_PROTOCOL.md.
Web-безопасность остаётся следующим блоком, этап ещё не завершён.

Веб-блок этапа 4: 172 passed в контейнере; прежние Query.get предупреждения
устранены переходом соответствующих API на Session.get. Реальные сетевые проверки
HTTP/Socket.IO и Chromium DOM-XSS прошли; результаты в docs/reports/stage4-web.txt.
CSRF включена по умолчанию и в регрессионных тестах. Финальная документация и
повторный итоговый MQTT-контроль ещё выполняются; этап 5 не начат.

Итоговый регрессионный контроль: 177 passed, без предупреждений. Повторно прошли
TLS/ACL (включая запрет publish у receiver), v2 tamper/replay smoke и replay
после force-recreate receiver. Проверены права новых каталогов/файлов 0700/0600.
Протокол docs/reports/stage4-final.txt; финальное обновление документации выполняется.

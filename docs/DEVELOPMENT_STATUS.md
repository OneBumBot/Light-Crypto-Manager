# Состояние разработки и план

Дата: 2026-11-08. Выполнены только этапы 0 и 1. Этап 2 **не начат** и требует
отдельной команды пользователя. Push и merge в main не выполнялись.

## Сохранённые этапы

| Этап | Результат | Git |
|---|---|---|
| 0 — безопасная исходная версия | Корневой Git/main, исключения, приватная копия оригинала, санация конфигурации и notebook outputs | `908dd56` — `chore: establish safe legacy project baseline` |
| 0 — сохранение прав файлов | Права исполнения трёх vendored Python-скриптов сохранены отдельным коммитом без переписывания истории | `c352d81` — `chore: preserve executable modes of vendored Ascon scripts` |
| 1 — инвентаризация | Файлы, существующая архитектура, проблемы, статусы и план | Ветка `feature/component-inventory`; коммит `docs: inventory existing LightCrypto Manager components` |

Точный хеш документационного коммита см. `git log -1` и итоговый отчёт. Хеш
не вписывается в содержимое самого коммита. В main осталась безопасная база;
ветка инвентаризации содержит только четыре новых документа.

## Статусы компонентов

«Существует» подтверждает наличие файлов, «частично реализовано» — неполный
сценарий, «не проверено» — нет достаточного запуска, «проверено тестами» имеет
ровно указанную область проверки и не распространяется на весь сервис.

| Компонент / возможность | Статус | Доказательство / предел |
|---|---|---|
| Корневой Git и безопасная база | существует | Два коммита в main, приватный оригинал с manifest, чистое состояние после этапа 0 |
| Publisher | частично реализовано | Генерация/шифрование/publish написаны; зависимости и импорт не разрешены |
| Запуск publisher на Raspberry Pi OS/ARM64 | не проверено | Проверки проведены на x86_64 |
| Настоящий MQTT broker / Mosquitto | отсутствует | Нет сервера/конфигурации в репозитории |
| Receiver в brocker | частично реализовано | Подписка/пороговые правила/INSERT аномалий; SQL и обработка ошибок требуют исправлений |
| Сквозной MQTT обмен | не проверено | Broker и клиентские зависимости не запускались |
| Notebook экспериментов | существует | 13 ячеек RF/IF, исторические метрики просмотрены, не воспроизведены |
| Датасет, готовые модели и preprocessing artifacts | отсутствует | Есть только код загрузки CSV и joblib.dump |
| Online ML / согласованные признаки | отсутствует | Сетевые признаки отличаются от temperature/humidity |
| Flask, формы и роли | частично реализовано | Код входа/регистрации и ролевой карты; API auth/socket требуют проверки |
| ORM предметной области | существует | 14 моделей, PK проверены по исходникам; фактическая MSSQL схема неизвестна |
| CRUD | частично реализовано | Нет POST, составные PK не поддержаны, ошибочные логгеры после commit |
| Сохранение телеметрии | частично реализовано | save_sensor_data отключена и не завершает транзакцию |
| Шаблоны, CSS, JS, realtime UI | частично реализовано | Макеты/графики/Socket.IO есть; браузер не запускался, обнаружены дефекты |
| Работа Flask/API/MSSQL | не проверено | Нет установленных зависимостей и предоставленного сервера БД |
| Локальный примитив Ascon-AEAD128 | проверено тестами | 81 PT/AAD случай: round trip, длина, отказы при изменении tag/AAD/key/nonce |
| Соответствие Ascon финальному SP 800-232 | не проверено | Нужны независимые KAT и сверка спецификации; self round trip недостаточно |
| genkat/writer | существует | Импорты на Python 3.14.9 успешны, полный генератор не запускался |
| Синтаксис Python и notebook | проверено тестами | compile() успешен для 9 .py и 13 кодовых ячеек; без исполнения приложений |
| FastAPI / PostgreSQL / Alembic | отсутствует | Целевая архитектура следующих этапов |
| Отдельный оформленный MQTT worker | отсутствует | Есть legacy receiver, нет выделенного сервиса/пакета/жизненного цикла |
| Policy Engine / профили / anti-replay / защищённые команды | отсутствует | Алгоритмические справочники БД не являются движком политики |
| «Магма» / проверенный профиль CRISP | отсутствует | Нет реализации или подтверждения требований |
| Docker Compose / CI / автоматический набор тестов | отсутствует | Локальные проверки аудита не являются готовым test suite проекта |

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

## Предложенный технический план — ещё не реализован

Перед каждым этапом: проверить чистый Git/сохранение предыдущего, создать отдельную
ветку от согласованной базы, менять только нужные файлы, выполнить относящиеся
проверки, обновить этот документ и сделать коммиты. Merge в main/push — только
по отдельному разрешению. Этап 1 остаётся несмешанным с реализацией.

| Этап / ветка | Конкретные коммиты | Критерий завершения |
|---|---|---|
| 2 `fix/reproducible-legacy-runtime` | `build: define reproducible component environments`; `fix: make legacy entrypoints and Ascon imports consistent`; `test: add legacy component smoke checks` | Выбран и проверен Python для x86_64/ARM64; раздельные зависимости с Paho/Email/ML, безопасный env example без секретов; main guards, единый источник Ascon, настраиваемый путь логов; импорт без сетевых побочных эффектов; синтаксис/Ascon independent KAT и smoke tests. Функциональный MSSQL запуск только при доступной тестовой БД, иначе честно зафиксированный блокер |
| 3 `feature/local-mqtt-compose` | `build: add local Mosquitto and component compose services`; `test: verify encrypted local MQTT exchange` | Настоящий broker, конфигурация/healthchecks, loopback-публикация портов, тестовые ключи только локально, воспроизводимый publisher → broker → receiver. Ошибочный пакет не ломает цикл; временный приём без БД выделяется явно, без заявления о готовой персистентности |
| 4 `fix/telemetry-protocol-security` | `fix: close critical legacy SQL and web vulnerabilities`; `feat: define validated versioned telemetry envelopes`; `test: cover malformed and tampered telemetry` | Параметризованный SQL, ошибки транзакций/логгеров, закрытые Socket.IO события, XSS/redirect/CSRF/debug; валидируемая схема, размеры, UTC, topic/device binding, crypto allowlist. До устранения критических проблем контур не открывать внешней сети |
| 5 `feature/postgres-mqtt-worker` | `feat: add PostgreSQL models and Alembic migrations`; `refactor: extract MQTT ingestion worker`; `test: verify transactional telemetry persistence` | Явные FK/индексы/составные ключи, seeds и миграции на чистой БД, worker lifecycle/reconnect, единая транзакция приёма, запись датчиков/аномалий, контракт истории; существующие шаблоны сохранены |
| 6 `feature/ml-inference-pipeline` | `docs: define observable ML feature contract`; `feat: export versioned preprocessing and anomaly model`; `test: reproduce anomaly evaluation` | Решение: собирать сетевые признаки либо обучать новую модель по телеметрии. Версия/хеш датасета, train-only preprocessing, split по времени/группам, сохранение schema/encoder/model/versions, воспроизводимые метрики и inference. Выход ML — score/сигнал аномалии |
| 7 `feature/adaptive-policy-engine` | `feat: enforce minimum crypto profiles and policy hysteresis`; `feat: authenticate profile commands and reject replays`; `test: verify policy transitions and command recovery` | Минимальный уровень защиты обязателен; устойчивые аномалии быстро усиливают профиль, снижение лишь после продолжительного стабильного окна; ML не выбирает алгоритм. Key/session/sequence, хранение replay-state, дедупликация, authenticated commands, подтверждение/повторы/rollback, restart tests; не ранжировать алгоритмы по названию без модели угроз |
| 8 `feature/fastapi-web-integration` | `feat: expose authenticated FastAPI telemetry and table APIs`; `refactor: connect existing templates to FastAPI`; `test: cover web roles and realtime flows` | Сохранённые шаблоны/CSS/графики; контракт авторизации и realtime, полный CRUD с составными PK, пагинация; роли/CSRF/socket/browser tests; отключение legacy Flask пути только после проверки паритета |
| 9 `feature/domestic-crypto-profile` | `docs: specify Magma profile and CRISP requirements`; `feat: implement verified domestic crypto profile`; `test: validate domestic profile vectors and interoperability` | Сначала источники требований/профиль: режим, аутентификация, key/nonce limits, anti-replay и совместимость; независимые векторы. «Магма» не объявляется полным CRISP; при неполноте требований это ограничение явно фиксируется |
| 10 `feature/system-validation` | `test: add integration security and load scenarios`; `docs: publish reproducible experiment and deployment procedures` | Полная цепочка Compose, fuzz/negative cases, перезапуски/потери/повторы, нагрузка и ARM64 замеры, фиксированные параметры экспериментов, документация ограничений и фактические результаты |

Порядок уточнён результатами аудита: согласование импортов и локальная проверка
Ascon нужны уже на этапе 2; безопасность legacy закрывается до внешнего доступа,
а replay/dedup полностью фиксируются до включения адаптивного управления.
Инфраструктура ограничена задачей: без Windows, SIEM и лишних сервисов.
Наличие «Магмы» само по себе не доказывает ни полноту CRISP, ни криптостойкость
всей системы; сравнение профилей требует явной модели угроз и требований.

Следующее разрешённое сейчас действие — проверка и фиксация документации этапа 1.
После этого работа останавливается до команды на этап 2.

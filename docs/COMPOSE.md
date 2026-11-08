# Локальный защищённый контур — этап 4

Этап 3 сохранён в коммите 5be5444. Текущая конфигурация использует только TLS/8883,
аутентификацию и ACL; старый plaintext listener отсутствует. Web остаётся Flask.
Образы закреплены digest, Python — 3.12.16. PostgreSQL не публикуется на хост,
HTTP/MQTT публикуются только на 127.0.0.1. Это локальный dev-контур.

## Новый запуск

Требуются Docker/Compose, Python 3 и openssl на хосте. Проверено с Engine 29.9.2,
Compose 5.6.1. Classic builder работает без buildx; предупреждение сохранено в отчётах.

```bash
mkdir -m 700 -p .local-runtime
python3 scripts/prepare_security.py --directory .local-runtime/security
python3 scripts/prepare_compose.py
docker compose --env-file .env.compose config --quiet
docker compose --env-file .env.compose --profile demo --profile web up --build -d --wait --wait-timeout 90
```

Генераторы отказываются перезаписывать существующие файлы/каталоги. На новой
установке родительские каталоги/материалы получают 0700/0600. Секреты генерируются
случайно и не печатаются. В .env.compose указаны POSTGRES_PASSWORD, FLASK_SECRET_KEY,
MQTT_SECURITY_DIR; ключи устройств находятся только в приватном registry.json.
Старый ASCON_KEY_HEX не используется MQTT-контуром. Не выводите обычный config:
он разворачивает значения секретного окружения; config --quiet безопасен.

Для отдельного тестового проекта можно задать --project, --mqtt-port 0,
--web-port 0 и --env-file .local-runtime/<name>.env; MQTT_SECURITY_DIR в этом env
должен указывать на соответствующий уже созданный приватный каталог материалов.
Узнать случайные порты: `compose port broker 8883`, `compose port web 5000`
с тем же --env-file. По умолчанию MQTT — localhost:8883, HTTP — localhost:5000.

## Сервисы и секреты

| Сервис | Действие |
|---|---|
| security-init | Однократно копирует только нужные файлы из приватного host-каталога в отдельные role volumes, назначает владельцев и 0600/0700 |
| postgres | PostgreSQL, постоянный volume, pg_isready healthcheck |
| init-db | Создаёт 14 исходных таблиц и дополнительную mqtt_replay_state; не мигрирует существующие колонки |
| broker | Mosquitto TLS/8883 после security-init; password_file, ACL, лимиты размера; healthcheck использует monitor/options file |
| receiver | После init-db/broker; TLS клиент, v2 validation, атомарный anti-replay/аномалии; ready после SUBACK |
| demo-setup | Профили demo/checks: явная фикстура raspb1/Device_ID=1 и smoke/Device_ID=2, алгоритм/причины; конфликты не перезаписываются |
| publisher | Профиль demo; отдельные credentials/ключ raspb1, постоянный SQLite sequence volume |
| web | Профиль web; отдельные read-only MQTT credentials, собственный PG replay consumer, HTTP /login healthcheck |
| smoke | Профиль checks; отдельные credentials/ключ smoke, постоянный sequence и сохранённый пакет для restart-проверки |
| tests | Профиль checks; pytest, реальные DB-схемы и тестовые клиентские зависимости; не production сервис |

Базовый up не создаёт фиктивных устройств: demo/checks включаются явно. Повторный
seed идемпотентен; при конфликте IDs/значений откатывает всю транзакцию. Пороги
аномалий сохранены. Receiver пишет только аномалии, sensor persistence — этап 5.

CA private key остаётся на хосте. Broker volume содержит серверный private key,
password hashes, CA/cert и monitor password; его UID — 1883. Клиентские role
volumes принадлежат UID 10001. Publisher/smoke не видят чужих паролей/ключей;
receiver/web видят ключи только разрешённых устройств. Security-init — короткий
trusted root процесс, обычные приложения непривилегированны. В images нет этих
материалов: host input монтируется read-only, файлы попадают только в volumes.
Тестовый сервис имеет набор тестовых credentials для отрицательных проверок.

ACL: publisher пишет только iot/sensors/raspb1; receiver/web читают raspb1/smoke
и не публикуют; smoke пишет свой topic и наблюдает demo; monitor пишет только
lightcrypto/health. APP_ENV=test + MQTT_INSECURE_TEST_MODE=1 отключают TLS только
в явно выбранном клиентском тесте; Compose не содержит plaintext broker режима.

## Проверки

После demo/web запуска:

```bash
docker compose --env-file .env.compose build tests
docker compose --env-file .env.compose run --rm tests
docker compose --env-file .env.compose run --rm --no-deps --entrypoint python tests -m scripts.mqtt_security_smoke
docker compose --env-file .env.compose run --rm smoke --expect-demo
docker compose --env-file .env.compose up -d --no-deps --force-recreate --wait receiver
docker compose --env-file .env.compose run --rm smoke --replay-only
docker compose --env-file .env.compose run --rm --no-deps --entrypoint python tests -m scripts.live_web_smoke
```

Smokе больше не удаляет replay-state: это постоянное состояние защиты. Для smoke
используется явно provisioned устройство, а проверка сравнивает относительное
число его аномалий. Сохранённый packet.json/SQLite находится в приватном smoke-state
volume. --replay-only повторяет пакет, сохранённый предыдущим успешным smoke.
Проверяется не только наблюдение publisher-пакета: replay-state receiver должен
подтверждать, что тот аутентифицирован и принят. Независимые consumers receiver/web
не блокируют друг друга и не принимают повтор у себя.

Для Chromium DOM-XSS проверки (отдельный test-tool, не runtime зависимость):

```bash
UV_CACHE_DIR=.cache/uv PLAYWRIGHT_BROWSERS_PATH=.local-runtime/browsers uv run --no-project --python .venv/bin/python --with playwright==1.56.0 python -m playwright install chromium --only-shell
UV_CACHE_DIR=.cache/uv PLAYWRIGHT_BROWSERS_PATH=.local-runtime/browsers uv run --no-project --python .venv/bin/python --with playwright==1.56.0 python scripts/check_dom_xss.py
```

Требуются uv и Python-окружение этапа 2; на проверенной машине Chromium запустился
с fallback binary Playwright для Ubuntu. Это реальные DOM проверки активного JS,
не полный аудит всех браузеров/страниц. В тестах CSRF не отключается. Изменяющие
API используют X-CSRFToken, Socket.IO — login session + auth.csrf_token.

Очищенные протоколы с командами и EXIT CODE:
[reports/README.md](reports/README.md). Для записи нового запуска:

```bash
python3 scripts/run_check.py --report docs/reports/local-check.txt --secrets-dir .local-runtime/security -- docker compose --env-file .env.compose run --rm tests
```

Runner удаляет известные секретные литералы, private-key блоки, пароли URL,
ANSI-коды и хвостовые пробелы. Перед публикацией отчёты всё равно проверяются.

## Сохранение состояния и Raspberry Pi

```bash
docker compose --env-file .env.compose --profile demo --profile web --profile checks down
```

Обычный down сохраняет PG replay-state, sender counters и security volumes.
Не удаляйте их при сохранении старых ключей. После потери/отката состояния нужна
новая эпоха/ключ и согласованное provisioning. По завершении этапа тестовый проект
lcm-stage4 остановлен **без удаления volumes**, чтобы сохранить anti-replay.
Для повторения используйте тот же приватный env/каталог и сохранённые volumes.

Publisher уже поддерживает MQTT_HOST/PORT/CA_FILE/USERNAME/PASSWORD_FILE,
DEVICE_ID, DEVICE_REGISTRY_FILE, PUBLISHER_STATE_FILE. На Pi передайте только CA,
password своего устройства и ограниченный реестр только с его ключом, все приватные
файлы 0600/каталог 0700; не передавайте CA private key или consumer credentials.
При генерации server certificate добавьте --server-name <DNS> / --server-ip <IP>.
Для доступа Pi потребуется явная публикация порта broker на нужный LAN-интерфейс
в deployment-конфигурации; стандартный localhost binding намеренно сохранён.
Код publisher менять для TLS/параметров подключения не требуется. ARM64 execution
не проверялось, сборка/производительность устройства не заявляются.

Ограничения: Flask dev server/local HTTP (для внешнего доступа нужен HTTPS),
нет Alembic/FK переработки, полноценной записи датчиков, outbox/exactly-once UI,
автоматической ротации/provisioning, Policy Engine, ML или CRISP. Формат v1
отклоняется; схема v2 и границы atomic admission — [MQTT_PROTOCOL.md](MQTT_PROTOCOL.md).

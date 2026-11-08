# Native runtime — актуально после этапа 4

Compose с готовым TLS/ACL/PG контуром: [COMPOSE.md](COMPOSE.md). Этот файл описывает
запуск отдельных процессов из корня репозитория. Историческая инструкция этапа 2
сохранена в fca2153; старые ASCON_KEY_HEX/неаутентифицированный MQTT больше не подходят.

## Окружение и web

```bash
uv sync --locked --all-groups
cp .env.example .env
```

Python 3.12.16, версии/хеши — uv.lock. Для отдельного устройства можно выбрать
только `uv sync --locked --no-default-groups --group publisher`; нужны NumPy/Paho,
shared protocol/SQLite/TLS используют стандартную библиотеку. Экспорты pip:
requirements/{publisher,receiver,ml,dev}.txt и src/web/requirements.txt.
ARM64 wheels проверялись на этапе 2, но реальный Pi не запускался.

Заполните .env локально: DATABASE_URL PostgreSQL/Psycopg, случайный FLASK_SECRET_KEY.
Этот файл не входит в Git. Native PostgreSQL должен быть отдельно доступен;
Compose по умолчанию намеренно не публикует его на хост.

```bash
uv run --locked --no-sync --env-file .env python -m src.web.app init-db
uv run --locked --no-sync --env-file .env python -m src.web.app serve
```

init-db идемпотентно создаёт 14 исходных таблиц + mqtt_replay_state, не заменяет
Alembic. Web по умолчанию без MQTT и на localhost:5000, debug=False. Для начальных
admin/operator/viewer задайте соответствующий BOOTSTRAP_*_PASSWORD локально:

```bash
uv run --locked --no-sync --env-file .env python -m src.web.app bootstrap-users
```

Пустые пароли не создают аккаунты; существующие пароли не меняются. Регистрация
создаёт viewer. Login/form/API/Socket.IO используют CSRF, logout только POST.
LOG_FILE включает файл при явном запуске, иначе stderr. Сеть/файловый лог не
создаются при импорте модулей. Native web с MQTT требует собственной роли web,
её password file и consumer registry; publisher credentials ему не подходят.

## Publisher / receiver и будущий Raspberry Pi

Задайте MQTT_HOST, MQTT_PORT=8883, MQTT_CA_FILE, MQTT_USERNAME,
MQTT_PASSWORD_FILE, DEVICE_REGISTRY_FILE. Publisher дополнительно требует
DEVICE_ID, соответствующий MQTT_PUBLISH_TOPIC и PUBLISHER_STATE_FILE.
Реестр должен содержать только ключи, необходимые конкретному процессу.
Пример .env.example рассчитан на publisher; файлы следует предварительно
provision локально из защищённого генератора/административного контура.

```bash
mkdir -m 700 -p .local-runtime/publisher
uv run --locked --no-sync --env-file .env python -m src.publisher.mqtt_pub
uv run --locked --no-sync --env-file .env python -m src.brocker.mqtt_brocker
```

Receiver требует PostgreSQL, registry всех разрешённых устройств и свою MQTT
read роль. Не используйте одну учётную запись для всех процессов. TLS проверяет
CA и hostname, fallback на plaintext отсутствует. На Pi достаточно доверенного CA,
password/registry своего устройства и постоянного приватного каталога счётчика;
CA private key и consumer passwords на устройство не передаются.

Формат v2, ограничения полей, счётчик/epoch и потеря состояния описаны в
[MQTT_PROTOCOL.md](MQTT_PROTOCOL.md). Полная запись датчиков/ML/Policy Engine
не добавлены; receiver сохраняет аномалии и replay-state. Автоматическая ротация
и production HTTPS web deployment не реализованы.

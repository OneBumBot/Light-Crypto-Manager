# Этап 2: локальный запуск на PostgreSQL

Выполнено по команде пользователя после инвентаризации. MSSQL заменена на
PostgreSQL уже в этом этапе; MSSQL-сервера и исходных данных нет. Это создание
новой БД по существующим моделям, **не перенос данных из MSSQL**. Шаблоны,
14 ORM-моделей и notebook сохранены. Alembic, переработка схемы, выделение worker,
FastAPI и Compose остаются отдельными следующими этапами.

## Окружение

Все команды выполняются из корня репозитория. Поддерживаемый для воспроизведения
интерпретатор — CPython **3.12.16**, зафиксирован в `.python-version`. Проверено
на Linux x86_64 с uv 0.13.6. Диапазон Python в pyproject задаёт допустимые версии
для разрешения зависимостей, а не подтверждённую тестами поддержку всех версий.

```bash
uv sync --locked --all-groups
```

uv создаёт локальную `.venv` и при необходимости скачивает выбранный Python.
Системный Python Raspberry Pi OS заменять не нужно. Для Pi требуется 64-битная
ОС (ARM64). Проверено разрешение готовых wheels publisher/receiver/web для
CPython 3.12 / aarch64-manylinux_2_28; реальное выполнение на Pi не проверялось.
32-битная ОС и ML на ARM64 этим результатом не покрываются.

Для отдельных компонентов:

```bash
uv sync --locked --no-default-groups --group publisher
uv sync --locked --no-default-groups --group receiver
uv sync --locked --no-default-groups --group web
uv sync --locked --no-default-groups --group ml
```

Каждый sync формирует выбранное окружение; для одновременной разработки используйте
`--all-groups`. `uv.lock` содержит точные версии, источники и хеши. Для pip
подготовлены экспортированные версии: `requirements/publisher.txt`,
`requirements/receiver.txt`, `requirements/ml.txt`, `src/web/requirements.txt`.
Они генерируются из lock, а не редактируются вручную:

```bash
uv export --locked --no-default-groups --group publisher --no-emit-project --no-hashes --output-file requirements/publisher.txt
uv export --locked --no-default-groups --group receiver --no-emit-project --no-hashes --output-file requirements/receiver.txt
uv export --locked --no-default-groups --group web --no-emit-project --no-hashes --output-file src/web/requirements.txt
uv export --locked --no-default-groups --group ml --no-emit-project --no-hashes --output-file requirements/ml.txt
```

Paho закреплён на 2.1.0, все клиенты используют Callback API VERSION2.
Единственный источник Ascon — сохранённый `src/web/ascon/ascon.py`; внешний
пакет pyascon не нужен. Web использует threading/simple-websocket; eventlet,
Flask-MQTT и pymssql из runtime-зависимостей удалены. Основные проверенные версии:
Flask 3.1.3, Flask-SocketIO 5.7.2, SQLAlchemy 2.0.57, psycopg 3.3.8, NumPy 2.5.4.

## PostgreSQL и конфигурация

Если сервер PostgreSQL уже есть, скопируйте `.env.example` в `.env` и заполните
DATABASE_URL, FLASK_SECRET_KEY и ASCON_KEY_HEX. Секреты генерируются локально;
ключ Ascon — ровно 32 hex-символа (16 байт), общий для трёх процессов.
URL должен иметь схему `postgresql+psycopg://`; `postgresql://` нормализуется
к ней. Специальные символы пароля в URL нужно percent-encode.
`.env` не читается неявно исходниками: его загружает `uv run --env-file .env`.
Возможно также явно экспортировать переменные в окружение процесса.

Для новой локальной БД можно использовать один контейнер PostgreSQL. Следующий
пример создаёт приватные файлы со случайными значениями и не выводит секреты.
При существующем `.env`/postgres-dev.env он останавливается, не перезаписывая их.

```bash
python3 - <<'PY'
import os
import secrets
from pathlib import Path

directory = Path('.local-runtime')
directory.mkdir(mode=0o700, exist_ok=True)
directory.chmod(0o700)
password = secrets.token_hex(24)
content = Path('.env.example').read_text()
content = content.replace('lightcrypto:CHANGE_ME@', f'lightcrypto:{password}@')
content = content.replace('FLASK_SECRET_KEY=\n', f'FLASK_SECRET_KEY={secrets.token_hex(32)}\n')
content = content.replace('ASCON_KEY_HEX=\n', f'ASCON_KEY_HEX={secrets.token_hex(16)}\n')
files = {
    Path('.env'): content,
    directory / 'postgres-dev.env':
        f'POSTGRES_DB=lightcrypto\nPOSTGRES_USER=lightcrypto\nPOSTGRES_PASSWORD={password}\n',
}
if any(path.exists() for path in files):
    raise SystemExit('Configuration exists; edit it locally instead of overwriting')
for path, value in files.items():
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write(value)
print('Local configuration created; secrets withheld')
PY
docker run --detach --name lightcrypto-dev-db --publish 127.0.0.1:5432:5432 --env-file .local-runtime/postgres-dev.env --mount source=lightcrypto-dev-pgdata,target=/var/lib/postgresql/data postgres:17-alpine
docker exec lightcrypto-dev-db pg_isready -U lightcrypto -d lightcrypto
```

После готовности БД:

```bash
uv run --locked --no-sync --env-file .env python -m src.web.app init-db
uv run --locked --no-sync --env-file .env python -m src.web.app serve
```

Интерфейс: `http://127.0.0.1:5000`. `init-db` явно вызывает create_all для 14
существующих моделей: повторный вызов допустим, но изменение существующей схемы
он не мигрирует. Имена таблиц/колонок сохранены с регистром и корректно цитируются
SQLAlchemy/запросами receiver. Внешние ключи и Alembic пока не добавлены.

Вход и регистрация работают с PostgreSQL. Начальные admin/operator/viewer теперь
создаются только при явно заполненных `BOOTSTRAP_*_PASSWORD`:

```bash
uv run --locked --no-sync --env-file .env python -m src.web.app bootstrap-users
```

Пустое значение не создаёт аккаунт, существующий пароль не сбрасывается. Пароли
не печатаются. Пользователь также может зарегистрироваться с ролью viewer.

По умолчанию WEB_MQTT_ENABLED=0: web запускается без брокера. Для подключения
к доступному брокеру установите 1 и задайте MQTT_HOST/PORT/USERNAME/PASSWORD.
Отдельные процессы запускаются так:

```bash
uv run --locked --no-sync --env-file .env python -m src.publisher.mqtt_pub
uv run --locked --no-sync --env-file .env python -m src.brocker.mqtt_brocker
```

Эти процессы требуют действующего MQTT-брокера; его установка и проверка полного
обмена относятся к этапу 3. Receiver требует предварительно созданной PostgreSQL
схемы и конфигурации устройств/тегов. Автоматические фиктивные устройства не
добавляются: без совпадения Tag_Name с device_id аномалия не записывается и
выдаётся предупреждение. Сохранены пороги temperature>60/humidity>70 и задержка
>0.5 с. Поиск конфигурации параметризован; вставка выполняется в engine.begin.

Publisher теперь отправляет UTC timestamp с offset. Legacy naive timestamp
receiver трактует как UTC; для старых источников с локальными часами нужна
явная последующая адаптация. Искусственная поправка +3 часа удалена.

По умолчанию логи идут в stderr. LOG_FILE включает файл в выбранном месте,
родительский каталог создаётся при явном запуске. Импорт модулей не открывает
лог-файлов и не подключается к MQTT/БД. Сохранённый глобальный Flask app может
импортироваться для проверок; рабочий путь запуска — указанный module entrypoint.

## Проверки

```bash
uv run --locked --no-sync pytest -q -m 'not postgres'
uv run --locked --no-sync ruff check src/publisher src/brocker src/runtime.py src/web/app.py src/web/config.py src/web/forms.py src/web/models.py tests
```

Для интеграционных проверок установите TEST_DATABASE_URL на выделенную PostgreSQL
с правом CREATE SCHEMA и запустите `uv run --locked --no-sync pytest -q`.
Тесты создают случайную схему `lcm_test_<uuid>`, используют её через search_path
и удаляют только эту схему после каждого теста. Без TEST_DATABASE_URL БД-тесты
явно пропускаются. Для секретной конфигурации тестов также используйте приватный
env-файл и `--env-file`; не передавайте пароль в аргументах команд.
В pytest задан `--tb=short`: подробный traceback стороннего драйвера способен
включить строку соединения с паролем.

Фактические результаты и границы проверки — в DEVELOPMENT_STATUS.md. Четыре
фиксированных KAT из [эталонного ascon-c](https://github.com/ascon/ascon-c/blob/main/crypto_aead/asconaead128/LWC_AEAD_KAT_128_128.txt)
(Counts 1, 2, 34, 35, получены 2026-11-08) находятся в tests/test_crypto.py;
тесты не загружают векторы из сети и не генерируют ожидаемый ciphertext тестируемым
кодом. Это независимая частичная сверка AEAD, не сертификация и не полный аудит.

## Сохранённые ограничения

Web — локальный dev server с debug=False; известные Socket.IO auth/CORS, XSS,
CSRF, составные PK и отсутствие POST остаются задачами этапа 4/8. Сохранение
телеметрии в web по-прежнему отключено; receiver пишет только аномалии.
Начальная БД пуста, поэтому графики не получают историю автоматически.
Тест чтения истории использует явно созданные тестовые LogJournal/SensorData.
ML не подключена, датасет и готовые модели отсутствуют. Notebook не обучался.
Docker Compose/Mosquitto, replay protection и Policy Engine здесь не добавлялись.

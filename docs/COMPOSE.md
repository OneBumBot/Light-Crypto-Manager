# Этап 3: локальный MQTT-контур

Существующие Python-компоненты запускаются в Docker Compose с настоящим Mosquitto
и PostgreSQL. Код web, шаблоны, модель БД, publisher и криптографический примитив
не перерабатывались. В receiver добавлен только сигнал готовности MQTT-подписки.

## Сервисы и порядок запуска

| Сервис | Назначение / готовность |
|---|---|
| postgres | PostgreSQL 17.11, постоянный volume, healthcheck pg_isready, без порта на хосте |
| broker | Mosquitto 2.1.2, конфигурация в deploy/mosquitto, volume данных; healthcheck проверяет QoS 1 publish |
| init-db | Однократный существующий init-db/create_all после готовности PostgreSQL |
| receiver | Существующий subscriber после успешного init-db и готовности broker; healthcheck ждёт положительный SUBACK |
| demo-setup | Только профиль demo: явная идемпотентная фикстура устройства raspb1, справочники и конфигурация |
| publisher | Только профиль demo: существующий генератор после demo-setup и готовности receiver |
| web | Только профиль web: существующий Flask с MQTT; healthcheck HTTP /login |
| smoke | Сервис проверок: реальный MQTT/DB маршрут, временные изолированные записи устройства |
| tests | Сервис проверок: pytest с PostgreSQL; отдельные случайные схемы для DB-тестов |

Базовый up запускает postgres/broker/init-db/receiver. Профили demo и web включаются
явно. У publisher проверяется запуск процесса; отдельного healthcheck доставки нет.
Готовность receiver означает подтверждённую подписку, а не непрерывную проверку БД.
При disconnect marker удаляется, при новом успешном SUBACK создаётся снова.

Сервисы используют имена `postgres`/`broker` внутри Compose network. На хост
публикуются только MQTT и HTTP, оба на 127.0.0.1; PostgreSQL доступна внутри сети.
Брокер допускает anonymous connections без TLS: это локальный учебный контур
этапа 3. Закрытие известных проблем транспорта и web остаётся этапом 4.

## Подготовка и запуск

Требуются Docker Engine и современный Compose с conditional depends_on/profiles.
Проверено: Engine 29.9.2, Compose 5.6.1, Linux x86_64. На данной машине buildx
отсутствует: Compose выдал предупреждение и успешно использовал classic builder.
BuildKit-функции в Dockerfile не требуются. ARM64-сборка/запуск не проверялись.

Из корня:

```bash
python3 scripts/prepare_compose.py
docker compose --env-file .env.compose config --quiet
docker compose --env-file .env.compose --profile demo --profile web up --build -d --wait --wait-timeout 90
docker compose --env-file .env.compose ps
```

Скрипт создаёт `.env.compose` с правами 0600 и случайными PostgreSQL/Flask/Ascon
секретами. Существующий файл не перезаписывается. Значения не печатаются; файл
исключён из Git и Docker-контекста. Это отдельная конфигурация, native `.env`
этапа 2 не изменяется. Шаблон — deploy/compose.env.example (секреты пусты).
Compose намеренно отказывает при пустых обязательных секретах. Не публикуйте вывод
обычного `compose config`: он содержит развёрнутые значения окружения; используйте
`config --quiet`. Переменные shell имеют приоритет над env-файлом.

По умолчанию HTTP — `http://127.0.0.1:5000`, MQTT — `127.0.0.1:1883`.
MQTT_BIND_PORT/WEB_BIND_PORT меняют только порт хоста; значение 0 выбирает свободный
порт. Его можно узнать через `compose port broker 1883` / `compose port web 5000`.
Например, отдельный контур для проверок создаётся без конфликта портов:

```bash
python3 scripts/prepare_compose.py --env-file .local-runtime/stage3.env --project lcm-stage3 --mqtt-port 0 --web-port 0
```

Каталог для указанного env-файла должен уже существовать; приватные каталоги
создавайте с правами 0700. Во всех дальнейших командах используйте этот же env-файл.

Demo-setup резервирует ID 1 для алгоритма, тега и устройства, причины 0/1,
дату конфигурации 2026-01-01. Совпадающие записи не меняются. При конфликте
значений транзакция откатывается, fixture завершается ошибкой; существующие данные
не перезаписываются. Автоматической demo-фикстуры в базовом профиле нет.
При ручном изменении идентификатора publisher требуется соответствующая
конфигурация TagJournal/DeviceConfiguration — универсальный provisioning ещё не сделан.

Начальных пользователей Compose не создаёт. Доступны существующая регистрация
viewer и отдельный bootstrap этапа 2. При необходимости начального администратора
передайте приватно заполненный env-файл процессу bootstrap-users; пароль не задавайте
аргументом командной строки. Web читает live MQTT в память, но сохранение сенсорных
значений остаётся отключённым, как и до этапа 3.

## Сквозная проверка

После запуска demo-контура:

```bash
docker compose --env-file .env.compose run --rm smoke --expect-demo
```

Без профиля demo используйте `run --rm smoke` без флага. Проверка:

1. Создаёт случайное устройство/тег в PostgreSQL без изменения demo-строк.
2. Берёт реальную encrypt_data из publisher и общий локальный ключ, публикует
   AEAD JSON через настоящий broker с QoS 1.
3. Ждёт аномалию от отдельно работающего receiver в PostgreSQL.
4. Отправляет некорректный JSON и пакет с изменённым тегом, затем валидный пакет.
5. Проверяет ровно две записи для своего устройства и продолжение обработки.
6. При --expect-demo также наблюдает сообщение отдельного publisher-процесса и
   успешно расшифровывает его. Все временные записи своего устройства удаляет.

У скрипта есть timeouts и ненулевой код возврата при ошибке. Вывод ошибок ограничен
типом исключения, без traceback драйвера с реквизитами. UUID тега укорочен до
размера существующего поля Tag_Name (30 символов); текущая длина — 26.
Проверка не подтверждает anti-replay или отсутствие потерь в ненадёжной сети.

Полный набор автоматических проверок в контейнере:

```bash
docker compose --env-file .env.compose build tests
docker compose --env-file .env.compose run --rm tests
```

В tests-образе есть pytest/Ruff из нового экспорта requirements/dev.txt. Runtime
не содержит dev/ML пакетов. DB-тесты используют уникальные схемы search_path и
удаляют только свои схемы; runtime receiver продолжает работать в public.

## Образы, данные и остановка

Python/Mosquitto/PostgreSQL образы закреплены digest в Dockerfile/compose.yaml;
Python runtime — 3.12.16. pip устанавливает экспортированные точные версии из
этапа 2, uv.lock не изменён. Приложения работают под UID/GID 10001, с init и
SIGINT для штатного завершения. PostgreSQL/Mosquitto сохраняют данные в volumes.

Dockerfile копирует исходники явно; .dockerignore исключает всё вне разрешённых
файлов и дополнительно исключает Git, архивы и кеши. Не копируются оригинальный
ZIP, classifier notebook, .local-baseline, .local-runtime, .env и вложенная .git.
Runtime содержит лицензию vendored Ascon. Отсутствие нежелательных файлов и
непривилегированный UID проверены в собранном образе.

```bash
docker compose --env-file .env.compose --profile demo --profile web --profile checks down
```

Обычный down сохраняет volumes и данные. Не добавляйте --volumes к рабочему
контуру, если не хотите удалить его БД/состояние broker. Для нашего отдельного
одноразового проекта lcm-stage3 тестовые volumes после проверки удалены;
чужие контейнеры, volumes, образы и глобальный build cache не очищались.

Фактические результаты: 108 passed, 2 прежних Query.get предупреждения; повторный
MQTT smoke прошёл после перезапуска broker и нового SUBACK receiver. Browser UI,
ARM64, ML, TLS/ACL, lossless delivery и нагрузочные сценарии не проверялись.
Подробный журнал результатов и исправлений — DEVELOPMENT_STATUS.md.

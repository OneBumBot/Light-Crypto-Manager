# Stage 10: предварительно заданный план

Baseline: `4ac5081a69199041fb8e34111b976da6c257ac93`, branch `feature/system-performance-validation`.
Только новые `lcm-stage10-performance-*` projects. Одновременно работает один cohort; повторное использование использованного состояния только вместе с исходными volumes/keys. Никакого down -v.

Исследовательские вопросы: throughput/задержка при 3/10/25 устройствах, устойчивость очереди, отличие ACK от effective, восстановление зависимостей. 50 — дополнительный cohort при достаточном запасе ресурсов. Базовый интервал .5 s/device; дополнительные 1 и 2 s при необходимости локализовать предел. Первые короткие прогоны 300 s, длительный 900 s; 1800 s необязателен. Порядок cohorts последовательный, не независимые статистические повторы.

Stop budget: available host RAM <8 GiB; free report filesystem <4 GiB; суммарный project working memory >8 GiB; CPU >800% одного core; backlog >5000; принятых сообщений >100000/run; reports >256 MiB/run; hard watchdog duration+180 s. Ресурсные ограничения Compose сохраняются. При остановке publishers прекращают выпуск, consumer drain ограничен 90 s, состояние сохраняется. Значения ниже лимита не доказывают отсутствие иных нагрузок хоста.

Проба ресурсов через Docker stats; SQL/HTTP каждые несколько секунд, sampling overhead входит в эксперимент. PG metrics кумулятивные, используем delta; Mongo count сопоставляется после drain. Исходная совокупность сообщений — opt-in bounded journal агента, связанный с PG по device/key_epoch/sequence. События publish и PUBACK разделены. Journal не является durable криптографическим ledger и при аварии может быть неполным. Неподтверждённые величины — not_measured.

Время: monotonic/perf_counter только внутри процесса; контейнеры Linux одного Docker host используют общие CLOCK_REALTIME. measured_at→received_at включает генерацию/очередь/транспорт/декодирование до timestamp admission, а не точный PG commit. delivered_at ставится после Mongo write в PG finish; измеряем верхнюю оценку длительности доставки, не Mongo commit timestamp. Не складываем несовместимые интервалы. Внешняя синхронизация/ARM не проверяются.

Отдельно: 3 независимых microbenchmark subprocess repeats, warmup, чередование Ascon/AES, 64/256/1024/реальный sensor JSON, равный AAD, fresh ephemeral keys. Per-run и per-message статистика разделены. p95 только n≥200, p99 n≥1000; CI не выдаём по коррелированным packets.

Fault tests проводятся последовательно, только лабораторные сервисы: Mongo/control/policy/PG/broker/device/receiver. Для каждого сохраняются timestamps/counters/backlog/effective before/after. UI проверяется реальным Chromium в малом/среднем cohort. Все отрицательные DOM fixtures явно отделены от настоящих MQTT переходов.

## Воспроизводимый запуск

Совместимый Linux/Docker ComposeV2, Python3.12–3.14, uv/OpenSSL, Docker доступ и свободная RAM. Host dependencies: `uv sync --frozen --group receiver --group web --group dev`. Для графиков дополнительно существующая `--group ml` (установка зависимостей не запускает обучение); эксперимент использовал matplotlib3.11.2. Никакой ML worker не включается. Chromium: существующий Stage9 Playwright1.56.0/browser cache; matplotlib для графиков. Нужен internet только для первоначальной сборки зависимостей. Для постоянного стенда хранить private inputs на устойчивом диске, вне Git:

```bash
.venv/bin/python -m scripts.performance_lab prepare \
  --directory .local-runtime/stage10/my-10 \
  --project lcm-stage10-performance-my-10 --devices 10
.venv/bin/python -m scripts.performance_lab start \
  --directory .local-runtime/stage10/my-10 --build
# При необходимости STAGE10_INTERVAL=1 или2 при start; существующее состояние не удалять.
timeout 480 .venv/bin/python -m scripts.performance_run \
  --directory .local-runtime/stage10/my-10 --seconds 300 \
  --output .local-runtime/stage10/reports/my-10-run1
.venv/bin/python -m scripts.performance_lab status --directory .local-runtime/stage10/my-10
.venv/bin/python -m scripts.performance_lab stop --directory .local-runtime/stage10/my-10
```

Новый стенд: новый project+directory с новыми keys. Продолжение: тот же directory/project, `start` без prepare. При отсутствии used state volume — ошибка recovery required, никакой переинициализации. SQLite counters не копировать между identities. Проектные secrets не печатаются; local URL в start output. Учётная запись `demo-admin`, пароль в приватном `accounts/admin.password` (не в Git/командной строке). `run` останавливает publishers после окна, даёт90s drain; повторный `start` сохраняет ledger и выдаёт новые nonce leases.

Отдельно реальные переходы/recovery:

```bash
.venv/bin/python -m scripts.performance_reliability \
  --directory .local-runtime/stage10/my-10 --output .local-runtime/stage10/reports/recovery1.json
# Только реальные sequential/concurrent switches, без service faults:
.venv/bin/python -m scripts.performance_reliability \
  --directory .local-runtime/stage10/my-10 --switch-only --output .local-runtime/stage10/reports/switches1.json
```

Publishers должны быть запущены перед этими probes. Все output paths новые. Не запускать второй cohort параллельно. `stop` сохраняет volumes/credentials. Нельзя удалять Docker volumes или source inputs для «нового старта». `/tmp` использовался в текущем эксперименте как приватная lab sandbox; это не устойчивое место для эксплуатации/host reboot. Сохранить credentials и исходные volumes вместе; потеря keys/state требует recovery, не reset.

Для новых runs collector проверяет расчётный бюджет публикаций по фактическому `PUBLISH_INTERVAL` работающих контейнеров (≤100000), фиксирует sourceSHA/hashes до окна, ждёт ограниченный drain и отсутствие incoming в течение10s. Source-window identity join и post-drain identity join разделены. Early prototype3/10/25 windows имеют собственные исходные метаданные и полностью сопоставленную formed population; их raw artifacts не переписаны.

После shutdown других тестов Outbox может содержать durable pending. Для проверки полной доставки запустить только PostgreSQL/Mongo/relay в том же project, дождаться committed=managed Mongo и pending/dead0, затем stop. Не считать pending потерей и не удалять queue/volumes. Private inputs текущих runs сохранены в `.local-runtime/stage10/private/lcm-stage10-performance-{base,small,medium,extended}`; реальные counters — в прежних именованных volumes.

Для итоговой сверки сформированных сообщений fault-cohort: `python -m scripts.performance_census --directories <private> --fault-report <reliability.json> --output <new.json>`. Это read-only full-journal→PG identity join; выводит source-unconfirmed и отдельно reconnect одного процесса. Использовать сохранённые original volumes; source journal не считается crash-durable криптографическим ledger.

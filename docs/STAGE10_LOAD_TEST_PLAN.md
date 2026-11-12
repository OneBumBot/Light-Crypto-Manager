# Stage 10: предварительно заданный план

Baseline: `4ac5081a69199041fb8e34111b976da6c257ac93`, branch `feature/system-performance-validation`.
Только новые `lcm-stage10-performance-*` projects. Одновременно работает один cohort; повторное использование использованного состояния только вместе с исходными volumes/keys. Никакого down -v.

Исследовательские вопросы: throughput/задержка при 3/10/25 устройствах, устойчивость очереди, отличие ACK от effective, восстановление зависимостей. 50 — дополнительный cohort при достаточном запасе ресурсов. Базовый интервал .5 s/device; дополнительные 1 и 2 s при необходимости локализовать предел. Первые короткие прогоны 300 s, длительный 900 s; 1800 s необязателен. Порядок cohorts последовательный, не независимые статистические повторы.

Stop budget: available host RAM <8 GiB; free report filesystem <4 GiB; суммарный project working memory >8 GiB; CPU >800% одного core; backlog >5000; принятых сообщений >100000/run; reports >256 MiB/run; hard watchdog duration+180 s. Ресурсные ограничения Compose сохраняются. При остановке publishers прекращают выпуск, consumer drain ограничен 90 s, состояние сохраняется. Значения ниже лимита не доказывают отсутствие иных нагрузок хоста.

Проба ресурсов через Docker stats; SQL/HTTP каждые несколько секунд, sampling overhead входит в эксперимент. PG metrics кумулятивные, используем delta; Mongo count сопоставляется после drain. Исходная совокупность сообщений — opt-in bounded journal агента, связанный с PG по device/key_epoch/sequence. События publish и PUBACK разделены. Journal не является durable криптографическим ledger и при аварии может быть неполным. Неподтверждённые величины — not_measured.

Время: monotonic/perf_counter только внутри процесса; контейнеры Linux одного Docker host используют общие CLOCK_REALTIME. measured_at→received_at включает генерацию/очередь/транспорт/декодирование до timestamp admission, а не точный PG commit. delivered_at ставится после Mongo write в PG finish; измеряем верхнюю оценку длительности доставки, не Mongo commit timestamp. Не складываем несовместимые интервалы. Внешняя синхронизация/ARM не проверяются.

Отдельно: 3 независимых microbenchmark subprocess repeats, warmup, чередование Ascon/AES, 64/256/1024/реальный sensor JSON, равный AAD, fresh ephemeral keys. Per-run и per-message статистика разделены. p95 только n≥200, p99 n≥1000; CI не выдаём по коррелированным packets.

Fault tests проводятся последовательно, только лабораторные сервисы: Mongo/control/policy/PG/broker/device/receiver. Для каждого сохраняются timestamps/counters/backlog/effective before/after. UI проверяется реальным Chromium в малом/среднем cohort. Все отрицательные DOM fixtures явно отделены от настоящих MQTT переходов.

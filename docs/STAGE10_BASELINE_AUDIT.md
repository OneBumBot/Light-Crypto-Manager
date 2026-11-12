# Stage 10 baseline audit

Исходная ветка `feature/system-integration-demo`, SHA `4ac5081a69199041fb8e34111b976da6c257ac93`; чистое дерево, новая `feature/system-performance-validation`. Main не изменяется. Alembic head `0009_component_heartbeat`. Полная baseline-регрессия в новых PG/Mongo: **715 passed / 0 skipped / exit 0**, 35.07 s, `reports/stage10/baseline-regression.txt`.

Последние UI-коммиты: `6457db8` скрывает Policy JSON в details и объясняет DRY_RUN; `4ac5081` заменяет дублирующий dashboard отдельной `/control` с выбором проверенного устройства, capabilities, подтверждением действия, timeline и разделением ACK/effective. Существующие GET monitoring и POST control переиспользованы. Криптопротокол не менялся. Эти изменения включены в baseline.

| Контур / исходник | Реальный предел / конфигурация | Что ещё требуется измерить |
|---|---|---|
| Stage9 provisioner | 3 software identities | Это предел demo adapter, не системы |
| Stage10 adapter | 3/10/25/50 независимых identities | Ресурсный предел хоста |
| Telemetry | JSON≤8192B, ciphertext≤4096B, AAD≤1024B | Длительность проверки разных payload |
| Mosquitto | TLS≥1.2, ACL; packet12288B/payload8192B; .5CPU/128MiB | Throughput и reconnect при нагрузке |
| Managed nonce | lease10000 sequence; общий reserved≤2^32−1; ≤10000 lease rows/device | Долгосрочное исчерпание не испытывается |
| Agent | interval .05..60s; inbox128; один процесс/device, .25CPU/128MiB | Формирование/очередь/PUBACK и ресурсная стоимость |
| Ingestion | один receiver .5CPU/256MiB; глобальный admission advisory lock; replay+Outbox transaction | Сериализация и стоимость pending count |
| PostgreSQL | 1CPU/768MiB; отдельные process pools (обычно SQLAlchemy5+overflow10); connection_timeout2s | Реальное число connections, contention |
| Outbox | одна relay .5CPU/256MiB; claim1 row, lease30s; retry12/backoff≤300s; idle.5s; retention disabled | Drain throughput/рост очереди; capacity не равно числу устройств |
| Mongo | 1CPU/768MiB; majority+journal, уникальный identity; read timeout2/3/5s | Stored после drain, history query/index |
| Monitoring | read-only repeatable-read; SQL2s; page≤100 default50, offset≤10000; bulk latest DISTINCT ON; TTL15s | Query plan, API latency по cohorts |
| Control | один worker .5CPU/256MiB; durable queue; device request limiter2s; deadline и protected ACK | Request→effective отдельно ACK; recovery под нагрузкой |
| Policy | DRY_RUN; batch32, sleep1s; 1CPU/256MiB; heartbeat TTL30s | Отставание событий и влияние на admission |
| Heartbeat | receiver2s/TTL10s; controlTTL10s | Heartbeat означает свежую проверку, не гарантию доставки |
| ML | disabled/untrusted; RF/IF research only | Live IDS качество не измеряется |
| Retention | автоматическое удаление истории отключено | Рост данных требует отдельной эксплуатационной политики |

Хост: 16 logical CPU, около31GiB RAM/23GiB available при старте, x86_64 Linux; отдельные CPU/memory limits сохраняются. Рабочие и прежние Stage8/9 volumes не подключены. Все profiles остаются Ascon/AES; никаких будущих российских названий в live registry/UI.

Гипотезы, не выводы: глобальный lock, pending count и latest DISTINCT ON могут ограничивать скорость при росте истории; pure Python Ascon дороже native AES в этом окружении; один relay может отставать при outage. Проверять измерениями/EXPLAIN. Не объявлять максимальную вместимость по `MAX_OUTBOX_PENDING` или успешным тестам.

Уточнение control delivery из `server.claim`/worker: claim одного device/command, lease5s, максимум12 attempts, backoff до10s, общий deadline15..300s (по умолчанию120s), PUBACK wait отдельно. DEVICE_READY/DEVICE_APPLIED audit и immutable telemetry receipt являются разными наблюдениями. Stage8 `benchmark_switching.py` —8s windows и малое n; исторический отчёт сохранён, его p99 не используется как убедительное tail доказательство Stage10. Новые bounded windows и raw samples хранятся отдельно.

Проверенные runtime settings — `reports/stage10/environment.json`: PostgreSQL max_connections100; Python/package/OpenSSL versions и SHOW parameters зафиксированы. Docker и collector имеют один Linux kernel (same_linux_kernel=true); номинальное разрешение CLOCK_REALTIME не выдаётся за измеренную accuracy. Mongo administrative listIndexes недоступен relay — это ожидаемая least-privilege защита; EXPLAIN снят отдельно внутри lab mongo с приватным root.password file, права рабочих ролей не расширены.

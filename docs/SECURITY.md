# Уточнения этапа 10

Криптографические протоколы, nonce construction, HMAC, replay/Outbox транзакции,
verified effective receipts, RBAC/CSRF и trust boundary ML/Policy сохранены.
Новых live AEAD нет; подготовка ГОСТ не является реализацией или сертификацией.

Подтверждены реальные TLS/ACL/replay и poison-message проверки при ограниченной
нагрузке. Ошибка PG при загрузке identity возвращает503 без подмены прав/сессии;
старые Policy events не становятся свежими от heartbeat. Аутентифицированный ACK
по-прежнему не заменяет новую AEAD telemetry. Policy остаётся DRY_RUN.

Новые стенды имеют независимые keys/state; nonce duplicates в наблюдаемых окнах0.
Исследовательский журнал агента отключён по умолчанию и не используется для
авторизации, nonce или replay. Poison probe резервирует новый authenticated boot
range вместо вывода следующего nonce из admission high-water. Старый риск был
внутренним ограничением test producer, а не доказанным сетевым повтором nonce.

Preservation проверяет исторические hashes, конкретные новые secret values в
Git/reports/runtime images и права private inputs. Это не внешний аудит и не
доказательство отсутствия любого неизвестного секрета. Все datasets/models/
frozen plans и прежние ключи сохранены. Планы MGM требуют отдельной проверки
bounds, providers, KAT, usage reservations и recovery до права активации.

Доказательства и ограничения: [STAGE10_RESULTS.md](STAGE10_RESULTS.md).
Ниже — исторические security notes.

# Stage 9: границы integrated dashboard

Новые monitoring read routes требуют sensor_data permission и используют bounded
PG snapshots; secrets/wire/control bodies не выдаются. UI строит DOM через
textContent и safe DOM API; текущие values инвалидируются при backend failure.
Admin confirmation не заменяет server RBAC/CSRF/capability/pending checks.
Flask request handler не публикует MQTT; HMAC/ledger/nonce/effective authority прежние.

Новая диагностическая component_heartbeats table не участвует в admission или
авторизации. Receiver SUBACK/connection state передаётся независимым bounded SQL
heartbeat; PG failure не приводит к ложному manual ACK. Worker/ML/Mongo failures
показываются отдельно, отсутствие ML не является подтверждённой нормой.

Stage 9 credentials генерируются заново в private directory; accounts setup получает
пароли через stdin. Private keys не копируются в images; used-volume guard не
позволяет молча создать пустой authority state при resume. Security свойства
проверены целевыми PG/Chromium/mutation/live-TLS сценариями, не внешним pentest.
См. STAGE9_RESULTS.md и STAGE9_DEMO_RUNBOOK.md. Ни auto ML control, ни scientific
доверенности RF/IF, ни физического Raspberry Pi/production claim не добавлено.

# Уточнение 8-fix: malformed telemetry

Подтверждённый дефект parser позволял JSON list/object в outer profile вызвать
TypeError до AEAD/admission. Receiver отключался без manual ACK; на отдельном
TLS/ACL стенде воспроизведены повторные подключения в 10-секундном окне.
Добавлена проверка точного строкового типа до dictionary lookup. Некорректные
пакеты теперь проходят существующий durable reject audit и manual ACK path;
инфраструктурные/commit errors по-прежнему оставляют пакет неподтверждённым.
Проверены последующая telemetry, PG replay/Outbox/effective evidence, Mongo и
отсутствие redelivery после явного receiver restart. Это свойства проверенных
сценариев, не обещание доступности при неограниченном потоке или отказе PG.
Аудит и воспроизводимые ограничения — MQTT_MALFORMED_INPUT_AUDIT.md,
STAGE8_FIX_RESULTS.md. Криптографические параметры и control HMAC не изменены.

# Безопасность этапа 8

Opt-in MANUAL_AUTHORIZED_CONTROL, отдельный Compose/control worker/device agent.
Два AEAD с независимыми keys, Ascon reference не изменена. GCM nonce выдаётся из
PG-backed boot ranges, rollback/missing device state fail closed. Command/status
защищены standard HMAC-SHA-256 с per-device/per-direction256-bit keys; TLS обязателен,
metadata от broker MAC не скрывает. Credential без MAC key не позволяет командовать.
Точные command/status ACL, web только HTTP→PG, admin RBAC/CSRF/rate limit.

PREPARE не применяет profile. ACK не делает effective. Только AEAD+AAD+replay+
outbox/effective receipt commit подтверждают фактический profile; после grace
старый запрещается. Нет auto rollback. Late authenticated ACK обновляет только
reported/time, не confirmed evidence. Никакого ML auto-switch/trusted повышения.

Модель доверия/ограничения: CRYPTO_KEY_AND_NONCE_MANAGEMENT.md, CONTROL_RECOVERY.md.
Не заявляются FIPS/constant-time/аппаратный anti-rollback/защита от владельца всей
PG authority. Реальные тесты/known-secret scan: STAGE8_RESULTS.md и reports/stage8-*.
Старые разделы ниже исторические; их отсутствие live channel заменено новым
явно включаемым manual layer, а не автоматическим управлением Policy.

# Дополнение безопасности этапа 7

Policy Engine работает в DRY_RUN и не получает control MQTT права/ключи.
Управляющие topics не созданы. Только Ascon-AEAD128 в реальном registry, минимальная
TLS/AEAD/v2 защита не отключается. Устройство не подтверждает применение: PG
CHECK не допускает Applied Configuration до отдельной реализации протокола.

Неаутентифицированные rejects не имеют device_id. Поддельный AAD не может создать
адресный риск. Trusted binding формируют только внутренние адаптеры на основании
AEAD-проверенного ingestion журнала; внешний API произвольных trusted signals
отсутствует. ML contract строго валидируется, mode и trusted_detector=false
сохраняются. Score не превращается в общую вероятность атаки.

Версии политики неизменяемы по hash; активация admin+CSRF и audit actor/time.
Rules — типизированные JSON параметры, без eval/SQL/Python. API ограничивает
размеры/пагинацию, login и sensor_data права; metrics — admin. DOM textContent
используется для причин, конфигураций и исходных событий. Ошибки БД общие503.

Полный дизайн будущих ключей/авторизации/anti-replay команд/TTL/ACK —
CONTROL_PROTOCOL_DESIGN.md. Симулятор authentic=True — тестовая предпосылка,
не реализация криптографической аутентификации. Не переносить simulator snapshots
в реальное Applied Configuration. Текущие PG credentials ещё общие с мигратором;
least-privilege roles и внешний аудит остаются отдельной задачей.

Далее исторические сведения этапов4–5; актуальный source/protocol не переписан.

---

# Дополнение безопасности этапа 5

TLS/password/ACL MQTT, AEAD v2, строгая валидация, CSRF, safe redirect, role и
Socket.IO проверки этапа4 сохранены. PostgreSQL telemetry_devices дополнительно
сверяет enabled/topic/device/epoch/profile с приватным key registry. Ключей и
паролей в outbox/telemetry schema нет; поля формируются allowlist.

Mongo auth включена; relay insert/find, web find, root отдельно. Unique key и
сравнение содержимого не дают признать конфликтующий duplicate успешным.
Outbox не открыт в table API; ошибки/metrics не выводят payload/credentials.
History требует sensor_data access; metrics — admin. Локальный Mongo traffic
внутри Compose пока без TLS, поэтому production deployment не заявляется.

QoS1 ACK следует PG commit; lease/claim и retry/dead восстанавливают проверенные
сбои, но не дают end-to-end exactly-once/lossless. См. OUTBOX.md и ограничения
KNOWN_ISSUES.md. Секреты/логи/конечные образы проверяет scripts/audit_security.py
(несколько --secrets-dir, --image); это поиск известных материалов, не полный аудит.

## Историческое описание этапа 4

# Этап 4: защищённый контур

Ветка: feature/security-hardening от 5be5444. Этап 5 не начат.

## Транспорт

По умолчанию Mosquitto слушает только TLS/8883, требует пароль и ACL. CA/server
сертификаты генерируются локально, с SAN broker/localhost/127.0.0.1. Для будущего
Pi добавьте DNS/IP брокера при генерации, установите доверенный ca.crt на Pi и
задайте MQTT_HOST/PORT/CA_FILE/USERNAME/PASSWORD_FILE; publisher менять не нужно.
Hostname verification не отключается. Минимальный TLS — 1.2.

```bash
python3 scripts/prepare_security.py --directory .local-runtime/security
python3 scripts/prepare_compose.py
# .env.compose: MQTT_SECURITY_DIR=.local-runtime/security
# Выполнять из корня репозитория.
docker compose --env-file .env.compose --profile demo --profile web up --build -d --wait
```

Родительский .local-runtime должен быть приватным (0700). Генератор отказывается
перезаписывать существующий каталог. Все сгенерированные файлы имеют 0600, каталог
0700. Сертификаты тестовые, срок 30 дней; CA private key остаётся только на хосте.
Пароли передаются mosquitto_passwd через stdin, не аргументами процесса.

security-init копирует файлы в отдельные volumes с UID 1883 (broker) и 10001
(клиенты). Обычные приложения не видят чужие пароли; publisher/smoke имеют ключи
только своего устройства, receiver/web — разрешённых устройств. Тестовый сервис
получает тестовые credentials для негативных проверок. Изображения не содержат
секретных материалов. PostgreSQL по-прежнему не публикуется на хост.

ACL: publisher пишет только iot/sensors/raspb1, receiver/web читают raspb1 и smoke,
smoke пишет только свой topic, monitor публикует только lightcrypto/health.
Healthcheck broker использует приватный options file, не пароль в командной строке.
Клиентский plaintext режим возможен только при одновременно APP_ENV=test и
MQTT_INSECURE_TEST_MODE=1; Compose не содержит plaintext listener/override.

Очищенные протоколы с командами/кодами завершения: docs/reports/stage4-*.txt.
Формат v2 и постоянный anti-replay реализованы: см. MQTT_PROTOCOL.md.
Web-защита завершена; финальные результаты — reports/README.md.

## Web: проверено

CSRFProtect включён для всех изменяющих HTTP-запросов, включая login/logout и
JSON API; fetch передаёт X-CSRFToken из мета-тега. Logout только POST и закрывает
Socket.IO своего сеанса. Socket.IO требует активного пользователя с правом читать
sensor_data, CSRF-токен и привязан к сеансу. Разрешены только same-origin запросы.
Каждое событие направляется проверенным sid, не broadcast; перед отправкой повторно
проверяются активность и роль пользователя в БД. Неизвестная роль не получает
неявных viewer-прав. Несколько HTTP-сеансов одного пользователя независимы.

API сохраняет существующие admin/operator/viewer права, использует явные списки
изменяемых колонок и проверку типов/длин/диапазонов. PK, служебные атрибуты,
неизвестные поля и составные scalar-ID отклоняются. Ошибки HTTP/БД не возвращают
SQL, exception text или stacktrace. Safe next разрешает только локальные пути.

В table_edit.html значения записей создаются через DOM/textContent/input.value,
а не динамический HTML. Старый table_edit2 наследует защищённый основной шаблон,
чтобы не сохранять второй опасный JS. Внешний вид и базовые сценарии сохранены.

Проверки: финальные 177 pytest прошли в Docker без отключения CSRF; сетевой HTTP/Socket.IO
smoke и реальный Chromium с 4 XSS payload прошли. В протоколе сохранены также
два неуспешных CSRF прогона: изоляция тестовых HTTP-сеансов требовала очистки
rendering-cache токена g в старой DB-фикстуре с внешним app context. Защита
приложения не отключалась. Web остаётся локальным Flask dev server; production
HTTPS/reverse proxy, внешний аудит и многопроцессный Socket.IO не заявляются.


Итог: выполнен только этап 4. После проверки тестовый Compose остановлен без
удаления state/security volumes. Push/merge не выполнялись. Ротация, полноценный
worker/persistence датчиков и Alembic не добавлялись. Для воспроизведения и текущих
ограничений используйте COMPOSE.md, MQTT_PROTOCOL.md и KNOWN_ISSUES.md.

Источники API: [Mosquitto authentication](https://mosquitto.org/documentation/authentication-methods),
[Flask-WTF CSRF](https://github.com/pallets-eco/flask-wtf/blob/main/docs/csrf.md),
[SQLAlchemy PostgreSQL upsert](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#insert-on-conflict-upsert),
[Playwright browsers](https://playwright.dev/python/docs/browsers).

## Stage11: проверенные свойства и пределы

MGM tag/AAD/key/nonce negatives, independent RFC vectors и реальные MQTT malformed tests подтверждают отказ на проверенных входах без выдачи plaintext/admission. Explicit dispatch исключает unknown→Ascon fallback. Новые per-device32B keys не передаются в control packets, SQL/Mongo/API/images/logs; web role исключает MGM keys. Per-key grants и verification attempts имеют durable bounded accounting. ACK сам по себе не меняет verified effective; lost-ACK/UNKNOWN_OUTCOME recovery проверены настоящей telemetry.

Это не доказательство полной защищённости или сертификации ГОСТ. Experimental CT cipher и ветвления MGM не позволяют заявлять whole-provider timing resistance. Допуск ограничен изолированным Stage11 software lab; не production/multitenant/physical IoT. Сохраняются TLS, HMAC, replay, nonce reservations, RBAC/CSRF, Policy DRY_RUN и ML untrusted. [Ограничения provider](STAGE11_PROVIDER_SELECTION.md), [budget/recovery](KUZNYECHIK_NONCE_AND_KEY_BUDGET.md).

## Stage12 provider boundary and release restrictions

Kuznyechik one-shot remains default; explicitly enabled bounded local worker has no listening socket. Input/output frames, IDs, lengths, status, deadlines and request/lifetime limits are enforced. Serialized fresh cipher instances prevent mutable MGM sharing. No keys in argv/environment/logs, no plaintext on failed tag, no fallback to another profile. Worker restart cannot reset PG/SQLite nonce or usage authorities. Infra/provider failure stays distinct from InvalidTelemetry and does not justify acknowledging a failed durable commit.

This is lab-only engineering validation, not whole-provider constant-time assurance: a secret-dependent branch exists in pinned MGM GF code, confirmed for the recorded compiler/x86 binary. No exploit/constant-time certification claim. Persistent memory and GC zeroization limits are documented. Magma/Python research providers are not live registered;64-bit Magma budget/rekey gate failed for current continuous telemetry.

All prior TLS/ACL/HMAC/AAD/replay/Outbox/manual-control/effective-receipt/RBAC/CSRF boundaries retained. Policy DRY_RUN and trusted_detector=false unchanged. Isolated Stage12 image/log/API/report/private-permission and historical-preservation scans passed; finite scans are not universal proof of absence of secrets. [Side-channel review](STAGE12_SIDE_CHANNEL_REVIEW.md), [evidence](STAGE12_RESULTS.md).

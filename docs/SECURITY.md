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

# Stage 9 — чистый запуск и защита диплома

## Требования

Linux x86_64, Docker Engine + Docker Compose v2-совместимый CLI, доступ к Docker
socket, Python 3.12–3.14 (проверено 3.12.16), `uv`, OpenSSL, свободные CPU/RAM для
Postgres/Mongo/Flask/receiver/relay/workers и 3 Python agents. Для сборки нужен доступ
к pinned container images/Python packages; для браузерной проверки Playwright 1.56.0
и совместимый Chromium headless shell с системными библиотеками. ARM/physical Pi
этими проверками не сертифицированы. Все команды выполнять из корня checkout.

```bash
uv sync --frozen --group dev
# Новый уникальный project и НОВЫЙ приватный каталог; не каталог прежних этапов.
.venv/bin/python -m scripts.prepare_stage9_demo \
  --directory /tmp/lcm-stage9-demo-example --project lcm-stage9-demo-example
.venv/bin/python -m scripts.run_stage9_demo \
  --directory /tmp/lcm-stage9-demo-example start --build
```

Prepare отказывается перезаписывать каталог/использованный project. Создаются
независимые device/control keys, TLS CA/server, MQTT/SQL/Mongo passwords, три SQLite
и три непубличных user passwords. Никакие production secrets/volumes не нужны.
В shared security installer отсутствующие legacy identities не получают ACL.

Runner использует compose.yaml + compose.control.yaml + маленький compose.stage9.yaml.
Сборка runtime/tests, init-db применяет все Alembic migrations до
0009_component_heartbeat; затем TLS broker, PG/Mongo, receiver/relay/web/Policy,
idempotent provisioning, control worker и три agents. ML Worker не запускается.
Readiness ограничена по времени и требует настоящую первую AEAD telemetry/evidence
и Mongo delivery. Примерный бюджет запуска зависит от cold image build; запуск не
считает контейнер running доказательством telemetry readiness.

## Вход без постоянного публичного пароля

Runner печатает только loopback URL (`http://127.0.0.1:<allocated-port>`), роли и
расположение private files. Имена: `demo-admin`, `demo-operator`, `demo-viewer`.
Соответствующие одноразовые случайные пароли находятся в
`<directory>/accounts/{admin,operator,viewer}.password`, права 0600, каталог 0700.
Оператор читает файл локально и вводит пароль в браузере; не публиковать его в
README/отчётах/видеозаписи. Setup передаёт значения в one-off container по stdin,
не через argv/env, не ослабляет host permissions. При resume пароль не сбрасывается;
несоответствие существующего account вызывает отказ. Приватный directory хранить
вне Git и не включать в Docker build context.

## Сцены A–G

A. Viewer открывает URL, видит три provisioned/recent устройства с Ascon, отдельные
PG/Mongo/receiver/control/policy indicators. Открывает alpha, проверяет timestamps
и Mongo history, затем выходит.

B. Войти admin. Показать факты security и Policy DRY_RUN. UNKNOWN без ML допустим:
не подменять его ALERT. Физический threshold/delay/replay observation — факты с
оговорками, не доверенный IDS. Отсутствие ML score не означает норму.

C. В карточке alpha выбрать AES-128-GCM, объяснить ручной исследовательский выбор
без ранжирования силы, подтвердить dialog. Действие не следует автоматически
из рекомендации; требуется admin/CSRF и capability.

D. Наблюдать pending/commands/audit. READY/ACK видны как реальные события, 202 —
только durable intent. Дождаться EFFECTIVE_CONFIRMED и нового receipt/telemetry
ID; проверить actual AES-128-GCM record в Mongo history.

E. Вернуться к списку: beta/gamma остаются Ascon. В gamma AES отсутствует в picker;
server также отвергает unsupported switch.

F. Переключить alpha обратно на Ascon, дождаться новой receipt. Обновить страницу:
статус и история восстанавливаются из PG, а не из клиентского кэша.

G. Только оператор терминала изолированного стенда может остановить auxiliary
service. Например Mongo; в UI history unavailable, PG telemetry продолжается.
После restart relay догоняет очередь. Control/Policy outage отдельно не выключает
receiver; stale heartbeat виден спустя TTL. В UI нет кнопки crash/отключения TLS.

```bash
# Полная проверка, включая настоящий Chromium и ограниченные отказы сервисов:
PLAYWRIGHT_BROWSERS_PATH=.local-runtime/browsers uv run --no-project \
  --python .venv/bin/python --with playwright==1.56.0 python -m playwright install chromium
.venv/bin/python -m scripts.check_stage9_demo \
  --directory /tmp/lcm-stage9-demo-example --output /tmp/stage9-check.json --browser
# Если CI image не содержит browser system libs, установить их штатно заранее.
```

Checker не подставляет успешные device статусы: switch проходит HTTP→HMAC→настоящий
agent→ACK→AEAD admission→PG receipt→Mongo. Отдельные перехваты API используются
только как помеченные DOM injection/malformed truth fixtures. Отчёт output immutable;
повторному запуску дать новый output path. Browser flow начинает с verified Ascon;
если admin оставил AES, сначала выполнить нормальный обратный переход.

## Остановка и продолжение

```bash
.venv/bin/python -m scripts.run_stage9_demo --directory /tmp/lcm-stage9-demo-example stop
.venv/bin/python -m scripts.run_stage9_demo --directory /tmp/lcm-stage9-demo-example start
.venv/bin/python -m scripts.run_stage9_demo --directory /tmp/lcm-stage9-demo-example status
```

Stop сохраняет containers/volumes/keys. Resume использует тот же приватный каталог,
project, PG authority и SQLite. На новом boot agent получает новый PG range, не
возвращает остаток прежнего AES nonce range. `used-volumes.json` предотвращает
тихую переинициализацию потерянного state volume. Нельзя удалять этот marker,
SQLite, replay/lease/command rows ради запуска; нельзя использовать `down -v`.
Для новой демонстрации — новый suffix и новые ключи, не reset старой identity.

## Типичные ошибки

* Docker permission denied: предоставить доступ к Docker штатным способом, не
  менять permissions приватных keys/account files на world-readable.
* Registry conflict/account mismatch: остановиться; проверить выбранный project,
  directory и сохранённые данные. Runner не сбрасывает fingerprint/пароль.
* Missing used volume или missing device state: fail closed. Нужна reviewed
  recovery из CONTROL_RECOVERY.md либо новый независимый стенд с новыми ключами.
* Mongo unavailable: history недоступна; смотреть PG backlog, не объявлять
  разницу accepted/stored потерей до завершения delivery.
* Control stale: команды не подтверждены. Восстановить worker; не выставлять
  effective по ACK/HTTP 202. PREPARE-only expiry не имеет универсального reset.
* Policy stale/ML disabled: это не отказ криптоканала и не подтверждённая норма IDS.
* PG unavailable: UI.invalidate; восстановить исходный volume/WAL без rollback.
* Readiness timeout: приватный `last-command-failure.txt` содержит diagnostic
  stdout/stderr без intentional secret printing; проверить logs/status, не удалять
  state. При частично инициализированном стенде start повторяет только idempotent
  provisioning сохранённых volumes.
* Истекли тестовые TLS certificates (30 дней): reviewed renewal либо новый
  независимый стенд; не отключать проверку TLS и не сбрасывать counters/keys.
* Внешние CDN недоступны: основной dashboard/native charts/local navigation
  продолжают работать; advanced legacy pages могут сохранять прежние CDN зависимости.

HTTP Flask dev server публикуется только на loopback. Production reverse proxy/TLS,
операторская ротация, backup/restore и физические IoT требуют отдельного этапа.

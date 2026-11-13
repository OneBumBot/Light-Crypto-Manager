# Stage16 — единый безопасный demo

## Требования и первый запуск

Проверено на Linux x86_64, Python3.12.16, Docker Engine/Compose v2-compatible CLI (фактически Compose5.6.1), OpenSSL. Нужны Docker daemon, доступ к pinned package/container sources при первой установке/сборке, около4GiB доступной RAM и несколько GiB свободного диска. Preflight проверяет Docker/Compose, host modules, порт, explicit private /24, пересечения сетей, свободную RAM/disk, private permissions, project/used state и наличие images. Проверки минимальных порогов ресурсов не являются гарантией вместимости.

В корне чистого checkout:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements/receiver.txt -r requirements/publisher.txt -r src/web/requirements.txt -r requirements/dev.txt
.venv/bin/python -m scripts.stage16_demo preflight
.venv/bin/python -m scripts.stage16_demo prepare
.venv/bin/python -m scripts.stage16_demo start --build
.venv/bin/python -m scripts.stage16_demo status
.venv/bin/python -m scripts.stage16_demo smoke --output .local-runtime/stage16/demo-smoke-01.json
.venv/bin/python -m scripts.stage16_demo evidence --output .local-runtime/stage16/demo-evidence-01.json
```

По умолчанию новый project `lcm-stage16-final-demo-main`, private root `.local-runtime/stage16/demo`, subnet `10.216.16.0/24`, Dashboard **http://127.0.0.1:15016**, MQTT/TLS loopback18816→broker8883. Служебные соединения внутри Docker используют broker:8883. Открывать Dashboard нужно на том же host; HTTP UI не объявлен публичным HTTPS deployment. Go provider собирается внутри pinned Docker stage, host Go не нужен.

Prepare создаёт новые CA/certificates, MQTT/AEAD/HMAC secrets, device SQLite seeds и private accounts. Имена: demo-admin / demo-operator / demo-viewer. Пароли находятся только в `.local-runtime/stage16/demo/accounts/<role>.password` (0600). Откройте нужный private file локальным редактором; не включайте его в отчёт/скриншот. Runner не печатает пароли или ключи.

Start применяет существующие migrations, выполняет idempotent initial setup один раз, запускает компоненты в порядке dependencies и ждёт **новые** accepted PG/Mongo identities от всех трёх агентов. Старые записи/существование контейнера не засчитываются как ready. Выводит фактический loopback URL и честный optional Shadow status.

## Повторный запуск и остановка

На текущем workspace финальный demo уже подготовлен и остановлен: **не повторяйте prepare**, используйте resume.

```bash
.venv/bin/python -m scripts.stage16_demo resume
.venv/bin/python -m scripts.stage16_demo status
.venv/bin/python -m scripts.stage16_demo smoke --output .local-runtime/stage16/demo-smoke-02.json
.venv/bin/python -m scripts.stage16_demo evidence --output .local-runtime/stage16/demo-evidence-02.json
.venv/bin/python -m scripts.stage16_demo stop
```

Resume не создаёт новые ключи/начальный SQLite и не повторяет setup. Проверяются исходные private material hashes, volume identity/creation metadata, used SQLite integrity/counters и stop checkpoint. Image-declared Mongo configdb/Mosquitto log volumes записываются по фактическим container bindings и сохраняются; при resume проверяются и они. Это non-authoritative auxiliary paths, не PG data или Device SQLite. При отсутствии/замене used state — отказ до device startup. Не исправлять это пустой БД или reset epoch; требуется reviewed recovery/rekey. Marker не является защитой от владельца, согласованно подменяющего всё хранилище.

Stop останавливает только этот project, сначала agents, сохраняет логический checkpoint PG/SQLite и затем останавливает services. Volumes, keys, commands, replay state и receipts не удаляются. Smoke отдельно проверяет Outbox drain после остановки publishers; остаточный pending при нештатной остановке остаётся durable и может быть доставлен после resume. На измеренных штатных stop checkpoints pending=0. Status/evidence требуют доступных PG/Mongo; offline status не выдаёт старый snapshot за текущий.

Новый независимый demo на том же host — новое имя, root, подсеть и порты:

```bash
.venv/bin/python -m scripts.stage16_demo preflight --directory .local-runtime/stage16/new-show --project lcm-stage16-final-demo-newshow --subnet 10.216.20.0/24 --web-port 15020 --mqtt-port 18820
.venv/bin/python -m scripts.stage16_demo prepare --directory .local-runtime/stage16/new-show --project lcm-stage16-final-demo-newshow --subnet 10.216.20.0/24 --web-port 15020 --mqtt-port 18820
.venv/bin/python -m scripts.stage16_demo start --directory .local-runtime/stage16/new-show --build
.venv/bin/python -m scripts.stage16_demo stop --directory .local-runtime/stage16/new-show
```

Проверьте, что выбранная подсеть/порты свободны; preflight откажет при пересечении. `--web-port 0 --mqtt-port 0` допускают случайные loopback ports; используйте URL из start. Старые сети не удаляются даже при исчерпании auto address pool. Все evidence output paths должны быть новыми. Smoke переключает Alpha туда/обратно относительно текущего профиля; Beta/Gamma не меняет. Запускать команды из корня checkout.

## Роли, интерфейс и проверки

Admin переключает; Operator/Viewer только просматривают control. RBAC/CSRF не ослаблены. Страницы `/`, `/devices/alpha`, `/telemetry`, `/policy`, `/control`, `/research/shadow-ids`. Security events находятся в карточке устройства. В Policy различайте worker ready и evidence freshness. UNKNOWN при missing ML не является поломкой.

Автоматический `smoke` проверяет настоящий HTTP/CSRF→HMAC/TLS→PREPARE/ACTIVATE→ACK→target AEAD telemetry→PG receipt→Mongo path. Никакого AckSimulator/direct process_packet substitute. Ограничение evidence probe: до10 000 admitted rows на новом demo; это bound отчётного инструмента, не measured system capacity. Не удаляйте записи ради продолжения: используйте новый project для нового показа, сохранив старый.

Для дополнительной browser проверки нужны отдельные Playwright/Chromium dependencies (не нужны основному demo): `.venv/bin/python -m pip install playwright==1.56.0`, затем `.venv/bin/python -m playwright install chromium`. Запуск `python -m scripts.stage16_browser --directory ... --output <new-report.json>`. Реальные desktop/mobile checks работали с blocked external CDN: core UI не требует доступа к CDN для своих функций; Bootstrap-dependent legacy flows не заявлены полностью offline certified; вид может отличаться. Демо не вводит новый frontend framework.

## Необязательные исследовательские контуры

**Shadow в основном demo: OPTIONAL_RESEARCH_DEMO_UNAVAILABLE.** Capture namespace, current-source parity и trusted private model mounts здесь не provisioned. Наличие старых файлов на host не означает активный observer. Нет fake scores или fallback модели. Для отдельного разрешённого показа используйте [Stage15 runbook](STAGE15_RESULTS.md#воспроизведение-и-следующий-этап): новый root/project/subnet, approved private Stage14 artifacts, свежий parity PASS, затем bounded inference. Не копировать old nonce ledger, не скачивать models с URL. Это отдельный research stand, а не обязательная зависимость Stage16.

**Kuznyechik:** Stage16 project не проходит существующий lab-only release gate, и он не ослаблен. Отдельный воспроизводимый сценарий — [Stage12 integration](STAGE12_SYSTEM_INTEGRATION.md) либо [Stage11](STAGE11_RESULTS.md). Требуются свежий разрешённый project namespace, APP_ENV=test, LCM_KUZ_VALIDATION_AUTHORIZATION=1, новые256-bit keys, provider KAT, capabilities и nonce/usage authority. На host с исчерпанным Docker auto pool до первого start задайте свободный explicit /24 в freshly generated `research.compose.json` / `kuznyechik.compose.json` (только network IPAM, не environment gates/volumes). Схема JSON: `{"networks":{"default":{"ipam":{"config":[{"subnet":"<свободная private /24>"}]}}}}`; объединить с существующим override, не заменить весь файл. Этот отдельный запуск Stage16 заново не выполнял; исторические проверенные результаты сохранены. Magma не включать.

## Доказательства и завершение

[Сценарий показа](STAGE16_DEMO_SCRIPT.md), [приёмочная матрица](STAGE16_E2E_TEST_MATRIX.md), [результаты](STAGE16_RESULTS.md). Остановка — только `stage16_demo stop`; никаких down-v/prune/reset. CA лабораторные, срок30дней; истечение сертификата не исправляется отключением trust validation. Потеря crypto authority требует reviewed recovery. Этап17 — оформление текста и иллюстраций по существующим фактам, без добавления функций.

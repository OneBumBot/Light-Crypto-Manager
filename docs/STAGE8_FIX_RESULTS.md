# Этап 8-fix — фактические результаты

Дата проверки: 2026-11-11. Ветка `feature/adaptive-crypto-control-fix`.
Baseline `67eb3bcff937c2b0975b18444680e98af84e76fd` совпал с заданным;
исходная ветка `feature/adaptive-crypto-control`, дерево было чистым.
Версия финальных исходников и тестов: `36c022611a3bdc6dfbea0272fdeea95e14a4369f`.
Последующие коммиты содержат документацию/отчёты. Main остаётся
`c352d817386a17fb244d3567b287af0412eed4e4`; push/merge/rebase не выполнялись.

## Исправление и аудит

В `decode_packet` добавлена проверка `type(packet['profile']) is str` до поиска
в `BY_ALGORITHM`. Структура telemetry, параметры AEAD, nonce/replay/HMAC и SQL
migrations не менялись. Широких catch/подавления инфраструктурных ошибок не добавлено.

На точном исходном parser подтверждены `TypeError: unhashable type` для `[]`, `{}`,
`["AES-128-GCM"]`, `{"algorithm":"AES-128-GCM"}`. Тест требует именно
`InvalidTelemetry`: исходный код дал **8 failed, 14 passed, exit 1**, исправленный
принимает оба настоящих профиля и отвергает все заданные недопустимые типы/unknown
string. Проверены malformed AAD, бинарные поля и profile/tag binding.

Аудит всех десяти заданных модулей: [MQTT_MALFORMED_INPUT_AUDIT.md](MQTT_MALFORMED_INPUT_AUDIT.md).
Других подтверждённых сетевых TypeError/KeyError/AttributeError/OverflowError на
проверенных путях не найдено. Внутренние dispatch/producer/config APIs могут
выдать TypeError при нарушении их Python-контракта; сетевой путь туда проходит
через проверки типов. Ошибка Decimal export в новом тестовом probe исправлена
отдельно и не является сетевой уязвимостью приложения.

## Настоящий MQTT/TLS эксперимент

Только проект `lcm-stage8-fix-20261111`, новые credentials, private directories,
volumes, PG и Mongo. Python 3.12.16, x86_64, cryptography 50.0.2, OpenSSL 3.0.22;
Mosquitto TLSv1.3 зафиксирован broker logs. Настоящие receiver, relay, Flask,
control worker и три Device Agent; исходный parser временно монтировался только
в тестовый receiver. Рабочие/исторические БД не использовались.

| Сценарий | Отправлено / результат | Receiver / окно | Exit |
|---|---|---|---|
| Исходный parser, после корректного Ascon | 2 malformed (`[]`, `{}`); rejected=0 | 6 TypeError в логах, 5 новых подключений receiver за 10 s; последняя выборка incoming +5 | 0 — наблюдательный probe |
| Исправленный Ascon | 17 malformed → 17 rejected; 3 valid admissions, 1 duplicate replay | 0 unexpected errors, 0 новых соединений за ~11 s | 0 |
| Исправленный авторизованный AES | То же: 17 rejected, 3 accepted, duplicate admission=0 | 0 unexpected errors/новых соединений за ~11 s | 0 |
| AES + проверка persistent session | 17 rejected, 3 accepted, 1 replay | Explicit receiver restart; ещё 5 s без роста incoming/rejected/accepted/replay | 0 |
| Ascon + проверка persistent session | 17 rejected, 3 accepted, 1 replay | Explicit receiver restart; ещё 5 s без redelivery | 0 |

В каждом успешном окне: 9 outer-profile negatives, 5 AAD negatives, 3 binary-field
negatives. Три admissions — initial valid alpha, valid alpha после poison и valid
beta; beta остаётся Ascon. Снимки PG replay, Outbox count, effective profile/event,
security evidence count и Mongo (managed и всей коллекции) до/после malformed
совпадают. Ни fake effective receipt, ни device-bound rejected identity не создано.
После poison тот же следующий sequence успешно принят; точный повтор wire packet
даёт replay observation без повторной AEAD admission/Outbox/Mongo delivery.

Baseline подтверждает повторные подключения при конечном числе отправленных
poison messages в ограниченном окне, а не длительность неограниченной DoS.
В baseline не отправлялся последующий valid пакет; нельзя приписывать ему
неизмеренный исход. После исправления его приём проверен непосредственно.

Publisher PUBACK не засчитывался как application ACK. Доказательства: committed
rejected observations без identity, ingestion counters, unchanged admission state,
сохранённые broker/receiver logs, новая telemetry, duplicate replay и explicit
restart с тем же persistent `lightcrypto-ingestion`. После restart нет роста
counters из-за redelivery. Unit callback tests отдельно проверяют manual ACK
после reject audit и отсутствие ACK при PG/долговременном audit failure.
PG failure остаётся инфраструктурной ошибкой, а не InvalidTelemetry.

Артефакты: [mqtt-before.json](reports/stage8-fix/mqtt-before.json),
[mqtt-ascon.json](reports/stage8-fix/mqtt-ascon.json),
[mqtt-aes.json](reports/stage8-fix/mqtt-aes.json),
[mqtt-aes-qos-verified.json](reports/stage8-fix/mqtt-aes-qos-verified.json),
[mqtt-ascon-qos-verified.json](reports/stage8-fix/mqtt-ascon-qos-verified.json);
рядом `.txt`, `.logs.txt` и `.restart.logs.txt`.

## Control и recovery

[control-negative.json](reports/stage8-fix/control-negative.json): реальные
HMAC/incorrect key, TTL, unknown profile, key reference/type, command replay,
device/topic binding, malformed commands/ACK, contradictory/duplicate ACK,
forbidden publish/read ACL, HTTP RBAC/CSRF. SQLite state/command ledger до и после
совпадают; invalid command не породил ACK; PG effective/event/reported/ACK count
не изменились. Устройство продолжило telemetry. Подписанные отрицательные fixtures
намеренно обходят producer validation, чтобы проверять receiving boundary.

[recovery.json](reports/stage8-fix/recovery.json): **9 реальных сценариев, exit 0**:
device restart, stale SQLite restore, worker restart после PREPARE, lost ACTIVATE
ACK, broker outage, PG outage после intent, PG outage после device activation,
grace expiry + bounded manual reconciliation, missing SQLite (agent exit 1,
accepted=0). Эти ожидаемые exit 1 не являются неуспешной приёмкой.
PREPARE-only expiry и запрет ложного effective проверены PG/SQLite/AEAD тестом;
нового recovery protocol и автоматического downgrade нет.

[final-roundtrip.json](reports/stage8-fix/final-roundtrip.json): настоящий
Ascon→AES→Ascon, по 2 authenticated ACK на transition, новые PG evidence и Mongo
receipts, EFFECTIVE_CONFIRMED по telemetry, exit 0. Соседние beta/gamma не меняли
профиль. Policy worker реально DRY_RUN, applied state отсутствует.

[mongo-recovery.json](reports/stage8-fix/mongo-recovery.json): во время Mongo outage
принято ещё 27 событий; pending вырос 2→24. После остановки producers/восстановления
Mongo pending=0, managed PG Outbox=Mongo=13249; exit 0. Данные не удалялись.

[CONTROL_RECOVERY.md](CONTROL_RECOVERY.md) содержит операторские действия для
PREPARE-only expiry/lost READY, ACTIVATE uncertainty/lost ACK, grace expiry,
PG/device restore и lost SQLite. PREPARE-only остаётся fail closed без CANCEL;
reviewed новая эпоха/ключи нужны при недоказанной nonce/command authority, потере
state без свежей согласованной копии, rollback/compromise/исчерпании бюджета.

## Regression и поведенческие мутации

* [input-unit-final.txt](reports/stage8-fix/input-unit-final.txt): **373 passed,
  3 PG skipped**, exit 0; в полном Docker suite эти PG проверки выполнены.
* [regression-final.txt](reports/stage8-fix/regression-final.txt): **703 passed,
  0 skipped, exit 0**, 34.54 s. Исходные 401 проверки сохранены, добавлены 302.
  AES/Ascon KAT, telemetry/replay/outbox/Mongo, control, recovery, policy/web,
  прежние 7.5b-fix research/hardening tests включены без сокращения набора.
* [static.txt](reports/stage8-fix/static.txt): `ruff check src tests scripts`, exit 0.

Первый полный прогон: **702 passed, 1 failed, exit 1**
([regression.txt](reports/stage8-fix/regression.txt)). Старый concurrent ML-storage
тест индексировал временный `None` от claim_one. Реализация при locked recheck
сознательно допускает такой результат; worker poll повторяет попытку. Тест теперь
повторяет claim не более 5 s и всё так же требует 8 уникальных jobs, fencing и
model-version isolation. ML runtime не изменён, тест не удалён/ослаблен до одного
claim. Прежний race-completion regression также выполнен.

Исследовательское/производственное обучение RF/IF не запускалось, frozen holdout
не открывался. Полный прежний suite включает synthetic fixture `.fit()`/export/
evaluation в временных каталогах; эти существующие тесты сохранены. Их временные
модели не являются новыми исследовательскими артефактами и не дают права actuation.

[mutations JSON](reports/stage8-fix/mutations.json): все **14/14** обнаружены
поведенчески, baseline exit 0, каждый mutant exit 1. Исходные 9 mutations этапа 8
сохранены, добавлены 5. Ни SyntaxError, ни import/dependency failure не засчитывались.
В JSON для каждого приведены test node, injected defect, expected/observed и traceback.

| Injected defect | Проверяющий тест (модуль/функция) | Ожидание / фактическое обнаружение |
|---|---|---|
| Убран exact outer profile guard | telemetry_security / outer_profile_exact_rejection | InvalidTelemetry обязателен / unhashable TypeError, 8 failures |
| reject выдаёт TypeError | telemetry_security / outer_profile_exact_rejection | InvalidTelemetry обязателен / TypeError, 22 failures |
| Нет AAD profile binding | telemetry_security / aad_profile_binding_before_decrypt | reject до decrypt / DID NOT RAISE InvalidTelemetry |
| Нет key_reference validation | control_protocol / authenticated_malformed_command_preserves_sqlite | ValueError и unchanged ledger / malformed command принят |
| ACK после PG failure | ingestion_ack / pg_failure_disconnects_without_ack | ACK запрещён / Mock assertion: ACK вызван |
| Нет HMAC проверки | control_protocol / control_authenticated_direction_and_device | ValueError / DID NOT RAISE |
| Нет command replay guard | control_protocol / monotonic_replay_gap_rejected | ValueError / DID NOT RAISE |
| ACK устанавливает effective | control_storage / effective_requires_real_telemetry_and_ack_loss_does_not_downgrade | остаётся Ascon / unexpected AES assertion |
| Нет device binding | control_protocol / authenticated_claimed_device_mismatch | ValueError / DID NOT RAISE |
| Нет capabilities gate | control_storage / capability_rejection_creates_no_command | ValueError / DID NOT RAISE |
| Разрешён overlapping nonce range | control_recovery / server_range_rollback_is_detected_on_device | ValueError / DID NOT RAISE |
| Преждевременный SQL commit | control_recovery / ack_transaction_rollback_does_not_queue_activate | одна команда после rollback / 2 != 1 |
| Принят contradictory ACK | control_recovery / forged_and_mismatched_ack_do_not_activate | ValueError / DID NOT RAISE |
| Игнорируется AES tag failure | aes_profiles / aes_rejects_modifications[tag] | InvalidTag / DID NOT RAISE |

## Неуспешные подготовительные попытки

Они сохранены и не считаются успешными проверками:

* `startup.txt`, exit 1: worker health до provisioning; после setup/live agents
  все сервисы healthy. В рабочий контур не обращались.
* `mqtt-aes-qos.txt` и `mqtt-aes-qos-retry.failure.txt`, exit 1: global Mongo count
  включал сохранённые regression fixtures; остановка до poison injection. Oracle
  исправлен без удаления fixtures; проверяет managed count и общий delta.
* `mqtt-aes-qos-final.failure.txt`, exit 1: core poison probe прошёл, но SQL SUM
  вернул Decimal в новом counter exporter; explicit restart ещё не выполнен.
  Исправлено exact int export, затем полный сценарий прошёл в `*-verified.json`.
* `mongo-recovery-preflight.txt`, exit 1: неверное ожидание pending=0 при активных
  publishers. Исправлено измерением in-flight baseline, требованием роста при
  outage и обязательным pending=0 после quiescence/recovery.

## Сохранность и пределы выводов

[preservation.json](reports/stage8-fix/preservation.json): 764 исторических
приватных файла, 194 старых Git-отчёта и 88 защищённых исходников/конфигураций
совпадают с архивными/baseline hashes. Reference Ascon, AES параметры, ключи,
миграции, replay, Policy/ML sources, PCAP/models/plans/benchmark history не менялись.
Main не изменён. Финальный quiescent snapshot: **18486 accepted = delivered =
managed Mongo**, pending=0, replay observations=5, rejected=87,
rejected с неподтверждённой identity=0. Всего Mongo=18536: ещё 50 документов
сохранены двумя полными regression runs (по 25 fixtures: Mongo/history/ML-worker).
Это не 50 admissions main receiver и не malformed telemetry. Подробности:
[final-state.json](reports/stage8-fix/final-state.json). Значения включают обычную
telemetry трёх software agents за весь стендовый запуск, а не только poison окна.

[secret-audit-final.txt](reports/stage8-fix/secret-audit-final.txt):
known legacy/current secret scan Git/history/reports/images и права private
material. [runtime-isolation.json](reports/stage8-fix/runtime-isolation.json):
source hashes, отдельные volumes/networks, фактические CPU/RAM limits.
[shutdown.json](reports/stage8-fix/shutdown.json): тестовые контейнеры остановлены,
volumes/credentials сохранены. `docker compose down -v` не выполнялся.

Это целевые negative/mutation/recovery проверки software agents на x86_64, короткие
окна наблюдения. Не заявляются защита от неограниченного потока, внешний аудит,
ARM/физические устройства, универсальный remote repair или отсутствие всех DoS.
703 passed не является самостоятельным доказательством защищённости. Policy
остаётся DRY_RUN; RF/IF — RESEARCH/DEMO, trusted_detector=false. Этапы 9/7.5c,
новые алгоритмы, FastAPI и автономный crypto control не начаты.

## Команды и воспроизведение

Все команды из корня репозитория. Приватный env находится вне Git:
`/tmp/lcm-stage8-fix-20261111/compose.env`. Каталог создавался новым, генератор
отказывается перезаписывать существующий. Для нового запуска выбрать новый suffix.
Полные command arrays/exit codes и hashes отчётов: `reports/stage8-fix/manifest.json`,
`final-roundtrip.json`, `control-negative.json`, `mongo-recovery.json`.

```bash
.venv/bin/python -m scripts.prepare_control --directory /tmp/lcm-stage8-fix-20261111 --project lcm-stage8-fix-20261111
# Далее DC — сокращение точной общей части использованных Docker-команд:
DC=(docker compose --env-file /tmp/lcm-stage8-fix-20261111/compose.env -f compose.yaml -f compose.control.yaml --profile control)
"${DC[@]}" build receiver tests
# PG/Mongo/TLS/receiver/relay/web/policy, затем setup; worker становится healthy после provision.
"${DC[@]}" --profile web --profile policy up -d postgres mongo broker receiver outbox-relay web control-worker policy-worker
"${DC[@]}" run --rm --no-deps --entrypoint python tests -m scripts.control_system_probe setup
"${DC[@]}" up -d --wait device-alpha device-beta device-gamma
.venv/bin/python -m scripts.check_malformed_mqtt_recovery --env-file /tmp/lcm-stage8-fix-20261111/compose.env --output /tmp/ascon-result.json
"${DC[@]}" run --rm --no-deps --entrypoint python tests -m scripts.control_system_probe switch-aes
.venv/bin/python -m scripts.check_malformed_mqtt_recovery --env-file /tmp/lcm-stage8-fix-20261111/compose.env --output /tmp/aes-result.json --profile aes-128-gcm-v1
"${DC[@]}" run --rm --no-deps --entrypoint python tests -m scripts.control_security_probe
.venv/bin/python -m scripts.check_control_system --env-file /tmp/lcm-stage8-fix-20261111/compose.env --output /tmp/recovery.json --extended
"${DC[@]}" run --rm --no-deps --entrypoint python tests -m scripts.control_mutations --output /tmp/mutations.json
"${DC[@]}" run --rm --no-deps --entrypoint python tests -m pytest -q -p no:cacheprovider
# Остановка без удаления volumes:
"${DC[@]}" --profile web --profile policy stop
```

Для baseline теста в `tests` и `receiver` временно монтировался read-only файл
`git show 67eb3bc:src/telemetry.py`; наблюдательный probe запускался с `--baseline`.
Не переносить эту подмену на рабочие сервисы. Самостоятельные fault probes требуют
точных предусловий; в частности recovery runner начинает с verified Ascon, а
control_security_probe требует предыдущую настоящую ACTIVATE/ACK.

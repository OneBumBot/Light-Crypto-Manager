# Этап 8 — журнал работы

Начато от f6f3c23, branch feature/adaptive-crypto-control. Рабочее дерево до
начала чистое, migration head 0006_policy_control. Подтверждены hard-coded
Ascon dispatch в telemetry/devices/outbox/Mongo. Исходная Ascon reference не меняется.

Первый блок: AESGCM 50.0.2, расширение telemetry v2. Проверка crypto/runtime/security
на host: 143 passed, 3 PG-dependent skipped (нет TEST_DATABASE_URL); это ещё не E2E.
Последующие результаты записываются по факту в STAGE8_RESULTS.md/reports.

Реальные PG + device-state checks: после устранения слишком длинного delivery
status и исправления изоляции Flask fixture sessions — 43 passed, exit0.
Первый isolated MQTT/TLS/HTTP E2E roundtrip Ascon→AES→Ascon прошёл, exit0;
обе EFFECTIVE_CONFIRMED имеют outbox event и Mongo record. Соседи Ascon, gamma
отвергает AES по capabilities. См. stage8-roundtrip.txt. Registry отмечает
подтверждение только software agent, не Raspberry Pi и не сертификацию.

Следующий блок: полный pytest с реальными PG/Mongo — 394 passed/exit0.
9 targeted code mutants выявлены поведением (предварительный runner до receipt
теста: 54 baseline checks); финальный mutation run будет повторён на acceptance.
Реальные recovery probes — 9 пройдены, включая grace expiry/reconciliation и
missing state. Часть ACK-negative сценариев требует свежего нормального ACK:
первый MQTT-negative report содержит 15 checks и не заявляет пропущенные ACK cases.
Добавлена 0008_control_evidence: только transition receipts, не копия сенсорной
истории. Проверены retention и rollback при отказе записи receipt. Архивные
records без packet digest не backfill выдуманными доказательствами.

Финал:401passed,0skipped/exit0 после late ACK correction. Фокусный тест до исправления
упал, после прошёл; реальная TLS переотправка сохранённого device ACK подтвердила
reported/time без изменения effective_event/confirmed_at. Real HTTP/Socket.IO,
12Chromium probes, TLS/password/ACL, Mongo validator upgrade2× с 12326 сохранёнными
documents иsource/image equality16files прошли.764archive hashes/141historical
reports неизменны. Оба новых проекта остановлены,38volumes суммарно сохранены.
Итоговая методика/ограничения/числа: STAGE8_RESULTS.md; benchmark pinned68c0767.

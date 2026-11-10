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

# Потоки данных и разные виды состояния

Device формирует настоящий AEAD packet, публикует по MQTT/TLS с собственным credential. Broker проверяет ACL. Receiver аутентифицирует AEAD/AAD до admission. PG транзакционно обновляет replay high-water, создаёт security observation и Outbox; Mongo получает idempotent projection через relay. Dashboard читает PG authority и Mongo history. PUBACK не равен PG commit или Mongo delivery.

Control: HTTP admin+CSRF → durable transition → HMAC PREPARE → authenticated READY → ACTIVATE → authenticated ACK → новая target-profile AEAD telemetry → committed receipt → EFFECTIVE_CONFIRMED. Command/transition/event IDs сохраняют provenance. Audit не подменяется генератором или AckSimulator.

Различаются configured profile, requested target, device-reported profile, verified effective profile и Policy recommendation. Нельзя переносить смысл одного поля на другое. Отсутствие данных/ML, stale evidence и service outage показываются отдельно от NORMAL.

Passive Shadow packet/session identity не является telemetry device/epoch/sequence identity. Отдельное хранилище и unbound attribution сохраняются; нет фиктивного переноса сетевых результатов в существующий ML feed. В основном Stage16 demo этот optional path не запущен.

[Telemetry diagram](diagrams/stage16/02-telemetry.mmd), [effective diagram](diagrams/stage16/04-effective.mmd).

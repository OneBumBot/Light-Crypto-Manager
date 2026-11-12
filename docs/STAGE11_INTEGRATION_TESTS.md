# Stage11 integration matrix

Исходный SHA `d226fbc…`; проверенные рабочие изменения фиксируются коммитами ветки `feature/kuznyechik-mgm-integration`. Отчёты до первого integration commit содержат baseline SHA с dirty worktree; их нельзя приписывать неизменённому baseline. Финальные прогоны имеют собственный source manifest.

| Проверка | Реальный путь / утверждение | Артефакт |
|---|---|---|
| Baseline | Все прежние unit/PG/Mongo, без пропусков | baseline-regression.txt:739 passed |
| Main chain | Admin HTTP, durable intent, HMAC/TLS, настоящий agent/SQLite, MGM/AES/Ascon, PG receipt, Outbox/Mongo | real-switching*.json:4 transitions/run |
| Poison MGM | 19 invalid packets, включая tag/AAD; 10 samples за≈11s; manual ACK evidence через отсутствие redelivery после receiver restart | mgm-poison.json |
| Control negatives | HMAC, TTL, identity/topic, malformed JSON, capability, ACK replay/key reference | control-security-final.txt; full pytest |
| Lost ACK | ACTIVATE ACK действительно подавлен agent fault hook; только READY ACK, effective по новой MGM telemetry | lost-ack.json |
| Deadline/reconciliation | Agent delay20s, TTL15s; UNKNOWN_OUTCOME сохраняет старый verified profile; admin observation window, новая MGM admission | lost-ack.json |
| Outages | Mongo, Control Worker, Policy Worker, PostgreSQL, broker, device, receiver | reliability.json:7 сценариев |
| Browser | Chromium DOM, viewer/admin, 4 переключения, соседние устройства, real service outages, XSS/малформированные API, stale/ACK-only | browser.json |
| Nonce/budget | fixed-width ICN, exact binding, parallel reservations, crash rollback, burned ranges, per-key bounds, verification attempts | test_kuz_integration.py |
| Migration | upgrade0009→0010 с реальными control/replay/receipts, повторный upgrade, отсутствие ложного backfill | test_additive_upgrade_preserves_existing_control_replay_and_receipts |
| Mutations | 20 целевых изменений во временных копиях, real PG schemas | mutations.json |
| Preservation | Исторические Git blobs и private archive hashes; independent keys; permissions; image/API/log scans; isolated volumes | preservation.json |

Mutation first run обнаружил пробел тестов: непосредственный Ascon KAT не видел подмену dispatch. Добавлен внешний Ascon dispatch-KAT; повторный прогон20/20 killed. Syntax/import/build failures не засчитываются. Для каждой мутации JSON содержит injected defect, test, expected/actual failure, exit code и traceback. Снятие Python budget guard дополнительно упирается в SQL CHECK: fail-closed сохраняется, но исключение меняется на DB error, что тест выявляет; это не утверждение обхода SQL-защиты.

Unit/integration прямые process_packet вызовы отдельно проверяют транзакционные эффекты. Основной switching/poison/browser E2E проходит через настоящий broker/receiver; AckSimulator не используется. Receiver PUBACK и application commit рассматриваются отдельно. Временные service outages не доказывают абсолютную доступность или физический MQTT presence.

Lost SQLite и stale local restore дополнительно проверены настоящим MGM agent: `sqlite-recovery.json`, exit0. Stale Ascon snapshot не получает разрешения на новую telemetry; missing SQLite завершает agent с exit1 без создания пустой БД. Восстановление только captured current MGM state требует нового boot grant. Существующие unit tests также сохранены; произвольный одновременный rollback PG+SQLite не объявляется решённым. Нельзя автоматически восстановить потерянные counters со старыми ключами.

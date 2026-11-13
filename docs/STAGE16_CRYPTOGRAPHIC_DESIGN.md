# Криптографический контур

Telemetry v2 и authenticated AAD связывают device/topic/epoch/sequence/schema/profile. Алгоритм выбирается explicit provider dispatch, неизвестный profile/backend не приводит к Ascon fallback. Ключи остаются в приватных файлах и role-scoped volumes; не передаются в control commands или API.

| Профиль | Key | Nonce / ICN | Tag | Статус |
|---|---:|---|---:|---|
| Ascon-AEAD128 | 128 bit | Существующая durable construction | 128 bit | Основной demo |
| AES-128-GCM | 128 bit | Существующая durable construction | 128 bit | Основной demo |
| Kuznyechik-MGM | 256 bit | 127 значащих bit, existing per-key budget | 128 bit | Только разрешённые software labs |

PG резервирует nonce ranges до передачи; Device SQLite хранит durable nonce high и command ledger. Restart не переиспользует диапазон. Replay admission, security observation, Outbox и matching effective evidence фиксируются одной транзакцией. MQTT QoS1 redelivery не является новой encryption invocation.

HMAC-SHA256 control v2 использует раздельные command/status keys. PREPARE не меняет local effective profile. ACTIVATE требует matching PREPARE. ACK означает authenticated device report, не самостоятельное подтверждение effective.

Kuz release требует APP_ENV=test, LCM_KUZ_VALIDATION_AUTHORIZATION=1 и разрешённого Stage11/12/13 project namespace плюс provider/key/capability/usage gates. Stage16 namespace намеренно не добавлен. Неизвестный LCM_KUZ_BACKEND fail closed. Нет whole-provider constant-time certification, ГОСТ-сертификации или production approval. Magma отсутствует в live registry; отрицательный результат по 64-bit security budget сохранён.

Источники: [Stage11](STAGE11_RESULTS.md), [Stage12](STAGE12_RESULTS.md), [nonce/key design](CRYPTO_KEY_AND_NONCE_MANAGEMENT.md), [security](SECURITY.md).

# Криптографический контур

Telemetry v2 и authenticated AAD связывают device/topic/epoch/sequence/schema/profile. Алгоритм выбирается explicit provider dispatch, неизвестный profile/backend не приводит к Ascon fallback. Ключи остаются в приватных файлах и role-scoped volumes; не передаются в control commands или API.

| Профиль | Key | Nonce / ICN | Tag | Статус |
|---|---:|---|---:|---|
| Ascon-AEAD128 | 128 bit | 128-bit CSPRNG, `os.urandom(16)` | 128 bit | Основной demo |
| AES-128-GCM | 128 bit | epoch32 big-endian ∥ sequence64 big-endian | 128 bit | Основной demo |
| Kuznyechik-MGM | 256 bit | 127 значащих bit, existing per-key budget | 128 bit | Только разрешённые software labs |

PG резервирует диапазоны authenticated sequence до передачи; Device SQLite хранит durable reservation high и command ledger. Restart не переиспользует диапазон sequence. AES nonce определяется этой парой epoch/sequence; MGM ICN = epoch31 в4-byte big-endian представлении с MSB=0 ∥ sequence в8-byte big-endian ∥ domain bytes `4c434d01` (`LCM\x01`). Ascon сохраняет прежний случайный16-byte nonce; sequence lease обеспечивает replay identity, но не является детерминированным Ascon nonce. Его uniqueness имеет вероятностный CSPRNG характер. Полная трасса Ascon IV в Stage16 не собиралась, поэтому отсутствие всех IV collisions не объявляется измеренным фактом. Конструкция не менялась. Replay admission, security observation, Outbox и matching effective evidence фиксируются одной транзакцией. MQTT QoS1 redelivery не является новой encryption invocation.

HMAC-SHA256 control v2 использует раздельные command/status keys. PREPARE не меняет local effective profile. ACTIVATE требует matching PREPARE. ACK означает authenticated device report, не самостоятельное подтверждение effective.

Kuz release требует APP_ENV=test, LCM_KUZ_VALIDATION_AUTHORIZATION=1 и разрешённого Stage11/12/13 project namespace плюс provider/key/capability/usage gates. Stage16 namespace намеренно не добавлен. Неизвестный LCM_KUZ_BACKEND fail closed. Нет whole-provider constant-time certification, ГОСТ-сертификации или production approval. Magma отсутствует в live registry; отрицательный результат по 64-bit security budget сохранён.

Источники: [Stage11](STAGE11_RESULTS.md), [Stage12](STAGE12_RESULTS.md), [nonce/key design](CRYPTO_KEY_AND_NONCE_MANAGEMENT.md), [security](SECURITY.md).

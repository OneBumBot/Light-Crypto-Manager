# Crypto provider boundary

`src/crypto_profiles.py`: profile ID выбирает ровно один `(encrypt,decrypt)` provider. Descriptor задаёт algorithm/key/nonce/tag sizes. Проверяются типы bytes, точные размеры, наличие provider и уникальные wire names. Неизвестный ID, включая unhashable JSON значения, → ValueError, на parser boundary → InvalidTelemetry. Нет Ascon else-fallback, trial decrypt, substring dispatch или перебора ключей.

Ascon использует прежний reference implementation; AES — прежний cryptography AESGCM; Kuznyechik — pinned Go `NewCipherCT` + MGM. Старые KAT неизменны; отдельный новый dispatch-KAT проверяет, что внешний Ascon vector проходит именно через новую таблицу providers.

Provider не выбирает identity/keys, не обновляет replay, не подтверждает effective и не принимает policy decisions. MGM subprocess получает только bounded binary frame через приватные pipes; fresh cipher instance на вызов, CGO отсутствует. Tag проверяется до выдачи plaintext. Ошибка процесса → ProviderUnavailable, не обычный bad packet. Размеры и timeout ограничены. KAT block operations используются только verification suite, не MQTT dispatch.

Private registry связывает ключ с device/profile/epoch; 32B Kuznyechik не допускает AES16B key. PostgreSQL отдельно управляет conservative usage reservations. Receiver admission/evidence/Outbox остаются одной транзакцией после успешного AEAD. Verification allowance расходуется отдельным durable commit до AEAD, чтобы malformed tag не обходил integrity budget.

Crypto descriptor означает наличие алгоритма, **не** разрешение control. Live manual eligibility отдельно ограничена policy registry, explicit Stage11 lab authorization, capabilities, provisioning, usage authority, текущим effective state, отсутствием pending и RBAC/CSRF. ML остаётся untrusted, Policy DRY_RUN.

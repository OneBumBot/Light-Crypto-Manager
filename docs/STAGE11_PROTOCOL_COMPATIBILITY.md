# Совместимость Stage11

Telemetry v2 fields и AAD schema сохранены. Новый уникальный wire name `Kuznyechik-MGM`; ciphertext включает полный16B tag, nonce — base64 от16B ICN. Ключ32B никогда не передаётся в MQTT. AAD связывает device/topic/epoch/sequence/schema/profile, outer profile совпадает с AAD. Unknown wire и неверные JSON types отклоняются до map lookup/provider. Размер packet8192B, AAD1024B, ciphertext4096B не увеличены.

Control HMAC v2, PREPARE/READY/ACTIVATE/ACK, TTL, key_reference=`profile_id:epoch`, command sequence, deadline, bounded reconciliation не изменены. Usage budget резервируется консервативно для всех выдаваемых range MGM-key device, поэтому новый wire lease field/version не нужен. ACK означает device report; effective подтверждает только новая AEAD admission с durable receipt.

SQL migration0010 аддитивна, исторические0001..0009 сохранены. Никакого secret storage или ложного backfill. Mongo validator расширяется отдельным `deploy/mongo/upgrade_kuznyechik.js` через collMod; strict/error остаются, неизвестные значения запрещены, документы/индексы не пересоздаются. Старые Ascon/AES документы читаются прежним API.

Default deployment не получает ручное включение Kuznyechik: оно требует отдельного Stage11 lab authorization. Capabilities alpha/beta расширены только при fresh preparation; gamma Ascon-only. Изменение используемого private config не является допустимым in-place rekey: fingerprint конфликтует, нужен reviewed epoch migration.

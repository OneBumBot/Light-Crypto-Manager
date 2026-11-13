# Stage16 — безопасность и восстановление

Основной стенд сохранил TLS trust, per-device ACL, AEAD/AAD/tag validation, HMAC v2, nonce/replay, RBAC/CSRF и исходные release gates. Реальные transport negatives: untrusted CA и неверный пароль отвергнуты; device не публикует соседу, web не публикует telemetry; replay принятого ciphertext не создаёт повторный admission/effective. Повреждённый tag реального захваченного ciphertext дал rejected+1, не Normal/replay admission; новая encryption invocation не выполнялась. Original signed ACK из SQLite проверен по HMAC и сопоставлен с PG body digest.

Control security probe проверил неверный HMAC/направление/identity/epoch/sequence/TTL/types, чужие topics, forged ACK и duplicate ACK. Несанкционированных дополнительных ACK/effective нет. Viewer/operator403, отсутствующий CSRF400, unsupported Gamma409. Browser/XSS checks: реальный Chromium, desktop/mobile, text rendering вместо HTML, source unavailable не становится success. No-auto-control DB query подтверждает models/events0, Policy applied0, actors только admin. Это не формальная сертификация безопасности.

## Измеренные ограниченные отказы

| Service | Hold, s | Весь case, s | После start до успешного наблюдения, s |
|---|---:|---:|---:|
| receiver | 2 | 9.841 | 2.339 |
| mongo | 5 | 20.693 | 2.350 |
| postgres | 4 | 10.472 | 2.351 |
| device-alpha | 2 | 9.914 | 2.334 |
| policy-worker | 32 | 42.052 | 2.531 |
| control-worker | pending request / 2s observation | 9.101 | 1.508 |

Граница: wall interval данного harness после успешного container start, наблюдение роста committed count и drain событий до restore-watermark. Включает polling/container-probe overhead, не универсальный RTO и не измерение физического первого packet. Receiver/PG/Mongo/device/Policy восстановлены. Для Mongo подтверждён durable pending во время outage и последующая доставка. PG outage дал HTTP503 без старого successful snapshot. При остановленном Control Worker durable request не получил ложный effective; после restart подтверждён настоящей telemetry. Policy unavailable не менял live profiles и не останавливал admission. Shadow failure здесь не исполнялся, поскольку optional component не активен.

Stop/resume проверен без provisioning: все прежние PG/Mongo identities, команды и receipts сохранены, SQLite command ledger/profile не сброшены, новые nonce ranges выше прежних. Один измеренный resume — 28.402s. Metadata fixtures missing marker/volume reference дали отказ до старта; ни volume, ни SQLite не удалялись.

## Auxiliary volumes и preservation

Финальный audit обнаружил новые anonymous image-declared volumes Mongo `/data/configdb` и Mosquitto `/mosquitto/log`. Они изолированы, но ранний comparator ошибочно относил их к архивным. Никакие старые hashes/volumes не изменились. Runner теперь записывает фактические bindings и CreatedAt этих двух строго ограниченных non-authoritative paths в used-volume manifest и проверяет их при resume. PG data и Device SQLite должны оставаться project-scoped; их нельзя объявить auxiliary. Старые и новые anonymous volumes не переносились и не удалялись.

Preservation сравнивает каждый baseline protected file/container и наличие старых volumes. Добавления разрешены только при доказанной принадлежности новым Stage16 container mounts; неизвестные additions или любое старое изменение остаются ошибкой. Это не побайтовый audit старых SQL volumes. Final reports: [preservation](reports/stage16/preservation-final.json), [security](reports/stage16/security-release-verified.json). Первоначальные failed audit traces сохранены.

Secret scan ограничен public files, `/app` использованных application images и последними1000 log lines каждого сохранённого нового контейнера. Не заявляется проверка всех исторических log bytes. Raw PCAP/model/key files не публикуются, old Stage14 holdout/model hashes не менялись. Потеря authority/неподтверждённый rollback требует reviewed recovery/rekey, не reset.

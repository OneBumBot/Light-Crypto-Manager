# Stage16 — оставшиеся ограничения

## A. Критические для demo

Открытых подтверждённых блокеров основного demo после проверок не осталось. Readiness, три агента, Ascon/AES manual switching, receipt evidence, RBAC/CSRF, Mongo delivery, stop/resume и clean-checkout запуск проверены реально. Окончательный verdict зависит также от regression/security/preservation checks, перечисленных в STAGE16_RESULTS; этот документ не заменяет их.

Устранённые реальные demo blockers: исчерпанный auto subnet pool (explicit disjoint subnet, старые сети сохранены) mobile overflow History (570→390px document) и неполный учёт image-declared auxiliary volumes (теперь подтверждённые bindings/CreatedAt проверяются без переноса данных). Ошибки ACK digest и русской UI status assertion принадлежали новым проверочным harness, исправлены без изменения протокола. Failed attempts сохранены.

## B. Некритические инженерные

- Ascon сохраняет legacy CSPRNG128-bit nonce; durable sequence leases не являются его детерминированным IV. Полная nonce trace Stage16 не собиралась; exhaustive collision absence не заявляется. AES/MGM используют существующие deterministic mappings.
- Research prototype, один host, три software agents, не ARM/Raspberry Pi, нет HA/production deployment.
- Kuz только в существующих разрешённых Stage11/12/13 labs. Stage16 не выдаёт новые capabilities и не получает MGM authority.
- Shadow в основном demo OPTIONAL_RESEARCH_DEMO_UNAVAILABLE: отдельные capture/model/parity scopes не provisioned. Его failure isolation подтверждал Stage15, не притворно повторено в неактивном Stage16.
- Отчётный Stage16 probe ограничен10 000 admissions. Это bound evidence tool, не ограничение/оценка system capacity. Старые записи не удаляются для обхода bound.
- Stop сохраняет durable pending; при outage не обещана немедленная доставка. Recovery timings — интервалы данного bounded теста, не гарантированный RTO или100% отказоустойчивость.
- Generated TLS CA/certificates действуют30дней; нет автоматической rotation. Утрата authority/неподтверждённый rollback требует reviewed recovery/rekey.
- Loopback HTTP Dashboard не является публичным HTTPS продуктом. Обязателен local-only deployment. Внешний Bootstrap CDN используется legacy UI; core demo functions проверены без него, legacy flows не заявлены полностью offline certified, вид может отличаться.
- Volume CreatedAt/material markers и файлы freeze не защищают от привилегированного владельца, согласованно переписывающего всё состояние. Preservation — hashes выбранных файлов и metadata старых Docker volumes, не audit каждого блока SQL volume.

## C. Научные

Stage14: packet RF recall49.04%, IF7.69%, только5 positive holdout sessions, один host, fingerprint purge, ограниченный shortcut audit. Stage15: five-feature parity для ограниченного Ethernet/IPv4/TCP contract; IF254/375 FP на новых corroborated Normal observations. Full-session transport aggregation отличается от purged known-labelled offline subset. Replay/QoS1 могут быть неразличимы по пяти features.

Нет independent-host generalization, production IDS, достоверной physical-device attribution анонимных попыток, ГОСТ certification или whole-provider constant-time audit. Score не probability атаки; controlled laboratory violation не реальная доказанная malicious attack. Нет нового обучения, retuning или старого holdout reuse. Policy DRY_RUN, trusted_detector=false, MANUAL_AUTHORIZED_CONTROL обязательны.

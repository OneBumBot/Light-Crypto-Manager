# LightCrypto Manager — описание финального прототипа

Разработан исследовательский прототип защищённой IoT-системы с механизмом ручного криптографического управления и экспериментальными средствами оценки сетевых аномалий.

Основной Stage16 demo: три настоящих software Device Agent процесса Alpha/alpha, Beta/beta, Gamma/gamma; TLS broker/ACL, receiver, PostgreSQL, Outbox relay, MongoDB, Flask, manual Control Worker и Policy DRY_RUN. Alpha/Beta поддерживают Ascon-AEAD128 и AES-128-GCM, Gamma — Ascon-only. Ключи устройств и алгоритмов независимы. Это не физические IoT/ARM устройства.

Kuznyechik-MGM реализован и проверен в прежних явно разрешённых software labs; Stage16 не расширяет его release gate. Magma не допускается к continuous telemetry. Shadow IDS — отдельный optional research stand, в основном demo OPTIONAL_RESEARCH_DEMO_UNAVAILABLE. Отсутствие моделей не мешает защищённой телеметрии или ручному control.

Пользователь видит реальные данные, подтверждённый effective profile, отдельные ACK/receipts, историю, состояние сервисов, очередь и freshness Policy. Модельные scores не являются доказательством атаки. Автоматического ML→Control нет. Итоговые факты и verdict — [STAGE16_RESULTS](STAGE16_RESULTS.md).

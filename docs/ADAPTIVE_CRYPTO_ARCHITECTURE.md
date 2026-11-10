# Этап 8 — реализованная архитектура (проверки в STAGE8_RESULTS.md)

Исходный HEAD f6f3c23. Изменения только в feature/adaptive-crypto-control.
Policy Worker сохраняет DRY_RUN; live control включается отдельно и только
MANUAL_AUTHORIZED_CONTROL. Web создаёт PG intent, не получает MQTT credentials.
Отдельный control worker доставляет committed команды, device agent исполняет,
receiver в своей admission transaction подтверждает effective конкретным outbox event.

Два AEAD без ранжирования стойкости: Ascon-AEAD128 и AES-128-GCM (cryptography
AESGCM). Telemetry v2 сохраняет поля/AAD; profile dispatch явный. Двойной приём
разрешён только в persisted transition с deadline на конкретное устройство.

## Выбранные границы

Команды не содержат секретов. Прикладная аутентификация — стандартный
HMAC-SHA-256 с независимыми 256-битными ключами на устройство и направление;
canonical JSON/domain/topic/device входят в MAC. Конфиденциальность метаданных
обеспечивает TLS, а не MAC: скомпрометированный broker видит команды, но без
control keys не может их подделать. Это разрешённая заданием альтернатива AEAD,
не самодельное шифрование; control nonces не нужны. Telemetry keys по MQTT не идут.

Чтобы восстановление старого device-state не повторяло AES nonce, agent при
каждом новом процессе требует свежий challenge-bound диапазон sequence от PG.
Диапазон durable резервируется до выдачи, после restart не восстанавливается
из локального файла. Счётчик общий между telemetry profiles, epoch/sequence
задают 96-битный GCM nonce. Лимит 2^32-1 использований на provisioned key epoch.
Локальный command/profile ledger durable; исчезновение ledger требует recovery,
не создаёт исходную конфигурацию молча. Один process lock на device-state.

Уже работающий agent продолжает телеметрию при отказе controller в пределах
выданного диапазона. При исчерпании или restart без нового grant — fail closed.
Нельзя одновременно гарантировать бесконечную offline работу и защиту от rollback
всех копий программного состояния без доверенного monotonic hardware. Restore
самой PostgreSQL authority со старыми ключами запрещён: нужна новая key epoch.

Источники: [SP 800-38D](https://csrc.nist.gov/pubs/sp/800/38/d/final),
[SP 800-232](https://csrc.nist.gov/pubs/sp/800/232/final),
[cryptography AESGCM](https://cryptography.io/en/latest/hazmat/primitives/aead/#cryptography.hazmat.primitives.ciphers.aead.AESGCM).
Статус реализации/тестов не выводится из этого документа-проекта.

```mermaid
flowchart LR
  Admin[Admin + CSRF] --> Intent[PG command intent]
  Intent --> Controller[Control worker]
  Controller -->|TLS + command MAC| Device[Device ledger + AEAD encoder]
  Device -->|authenticated ACK| Controller
  Device --> Broker[MQTT TLS broker]
  Broker --> Receiver[AEAD + AAD + replay admission]
  Receiver --> PG[PG outbox + effective receipt]
  PG --> Relay[Mongo relay]
  Relay --> Mongo[Mongo history]
  Policy[Policy DRY_RUN] -.recommendation only.-> Admin
```

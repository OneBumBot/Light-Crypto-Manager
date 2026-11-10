# Состояния реального переключения

PG risk/recommendations остаются в policy_* и DRY_RUN. Live authoritative records
в live_control_* — отдельная модель. Legacy Device_Configuration и Algorithm
не используются как доказательство реально применённого AEAD.

1. Admin RBAC/CSRF + explicit MANUAL_AUTHORIZED_CONTROL.
2. Проверка enabled device, подтверждённого baseline, capabilities/keys,
   конфликта pending transition, rate limit. Durable PREPARED_SERVER + PREPARE intent.
3. Worker публикует committed bytes. Реальный broker PUBACK → PREPARE_SENT/audit.
4. Аутентифицированный READY → DEVICE_READY audit и отдельный ACTIVATE intent.
   ACTIVATION_SENT обозначает durable authorization/ожидание результата, не applied.
5. Device сохраняет новый профиль, отправляет authenticated DEVICE_APPLIED.
   Это reported configuration, **ещё не effective**.
6. Receiver успешно проверяет новый AEAD/AAD/topic/device/epoch, admission/replay,
   outbox; в ТОМ ЖЕ PG commit фиксируется EFFECTIVE_CONFIRMED с event reference.
   Потерянный ACK не мешает подтверждению этой авторизованной активации по telemetry.

Grace существует только на device/transition/epoch, old/target profile и deadline.
Новый профиль разрешён только после durable ACTIVATE authorization; PREPARE его
не разрешает. После EFFECTIVE_CONFIRMED старый profile отвергается. Sequence
монотонен между профилями. Никакого global dual-decrypt или fallback.

Timeout/attempt exhaustion → UNKNOWN_OUTCOME, failure → RECOVERY_REQUIRED;
нет ложного rollback. По истечении окна неподтверждённый transition fail closed.
Неподдерживаемый запрос не создаёт команду. Только новый авторизованный transition
может вернуть AES→Ascon. Наличие профиля не означает иерархию криптостойкости.

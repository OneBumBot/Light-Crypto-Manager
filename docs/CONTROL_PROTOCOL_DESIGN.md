# Будущий защищённый control protocol: контракт, не live реализация

Command v1: command_id, device_id, command_type=set_profile, requested_profile,
policy_version, created_at, expires_at, command_sequence, command_epoch,
acknowledgement_id, correlation_id, status, schema_version. UUID канонические,
UTC aware timestamps; TTL>0 и <=300s. Строки/целые типизированы, bool не счётчик.

policy_control_intents хранит предложения; policy_control_counters резервирует
отдельные монотонные epoch/sequence на устройство в той же PG transaction, без
связи с telemetry replay-state или сброса при смене версии политики. Сейчас
создаются только proposed/unsupported; истёкший proposed становится expired.
Никакие pending/expired/отправленные сообщения не превращаются в applied.
Requested configuration в state — историческое намерение; актуальный lifecycle
нужно читать из policy_control_intents, expiry проверять по expires_at.

## Обязательства будущей live реализации

1. Аутентификация команды AEAD/signature, канонические authenticated metadata.
2. Отдельные control keys или проверенное криптографическое разделение доменов.
3. Отдельный controller principal, topic ACL и проверка права на целевое устройство.
4. Постоянный независимый anti-replay на устройстве, монотонные active epochs.
5. TTL, bounded retries, correlation и идемпотентность одного command_id.
6. Аутентифицированный ACK с привязкой к command/profile/epoch/sequence и actual
   configuration. Только он может подтвердить применение.
7. Persist-before-send, recovery/reconciliation после restart, timeout/error audit.

Ничего из этого не заменяется telemetry password или простой публикацией MQTT.
Live control topics/подписки/публикации не созданы. Контракт ещё не wire format
реального защищённого протокола; ключи/signatures/live device handler отсутствуют.

## ACK simulator

AckSimulator допускается только в тестах SIMULATION. authentic=True — явная
тестовая предпосылка, **не криптографическая проверка**. Проверяет авторизацию
simulation-controller, TTL, UUID, monotonic command epoch/sequence и дубликаты.
Snapshot/restore сохраняет simulator replay identity, до1000 команд; capacity
overflow явно отклоняется. Вывод содержит simulated_configuration, applied=NULL.
Эти snapshots не импортируются в реальное состояние устройств и не подписываются
от имени реального устройства. Unit-тесты проверяют restart/replay/expiry.

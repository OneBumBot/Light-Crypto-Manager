# Secure control v2 — manual authorized

Отдельный live protocol от policy/control_contract.py (тот остаётся simulation).
Формат envelope: ровно domain, direction, topic, body, mac. MAC — HMAC-SHA-256
на canonical JSON без mac; domain LCM-CONTROL-HMAC-SHA256-v2. Независимые
256-bit command/status keys на каждое устройство; compare_digest. Это стандартный
MAC, **не control AEAD**. Метаданные не секретны; TLS даёт конфиденциальность от
сетевого наблюдателя. Broker скомпрометирован: видит команды/может задержать их,
но не имеет ключей MAC для подделки. Телеметрические ключи по MQTT не передаются.

Body: schema_version=2, message_id UUID, device_id, kind, created_at, expires_at,
data. Kind command содержит command_id/transition_id/correlation_id UUID,
command_type=set_profile, phase PREPARE/ACTIVATE, requested_profile, source_version
admin-v1, controller_identity lcm-manual-controller, profile_config_version=1,
key_reference profile:epoch, command_epoch/sequence. ACK привязан к этим же
идентичностям, result и SHA256 всей команды. Boot lease_request/grant — отдельные
строго типизированные виды с request_id и случайным boot challenge.

TTL ≤300 s, future skew ≤5 s, UTC; запрещены лишние/дубли JSON fields, bool вместо
int, NaN/Infinity, неверные UUID/версии/subjects, неизвестные команды/profiles.
До аутентификации claimed device не является доверенным. Topic выбирает ровно
один разрешённый ключ, затем MAC и body binding проверяются; probing ключей нет.
Максимальный envelope 8192 bytes. Retained delivery отвергается; просроченность
проверяется независимо от MQTT retain flag.

Topics: lcm/control/DEVICE/command и lcm/control/DEVICE/status (ACK и boot status).
ACL перечисляет точные устройства: controller write command/read status;
device_USER read только свой command/write только свой status. Controller не
публикует telemetry; device не может командовать даже собой. Receiver/web/
research observer не получают command rights. Только MQTT/TLS с проверкой CA.

PG command intents/bytes фиксируются до network publish. Worker claims с lease,
повторяет те же bytes, ≤12 attempts/backoff≤10 s/expiry. Broker PUBACK отдельно от
READY/APPLIED ACK и verified telemetry. At-least-once transport, идемпотентное
исполнение; end-to-end exactly-once не заявляется.

## Stage11: третий target без изменения HMAC wire

`kuznyechik-mgm-v1` допускается только для явно provisioned Stage11 lab devices с key32B, capability, provider KAT/readiness и durable usage authority. Manual admin authorization/RBAC/CSRF, PREPARE/ACTIVATE, key_reference, TTL/replay/deadline и reconciliation сохранены. Каждый signed nonce grant консервативно расходует per-key MGM budget, даже если текущий профиль иной. DEVICE_APPLIED остаётся report, EFFECTIVE_CONFIRMED требует новой принятой AEAD telemetry. Нет автоматической ML/Policy команды.

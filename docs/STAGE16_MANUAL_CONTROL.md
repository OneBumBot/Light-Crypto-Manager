# Ручное управление

Только Admin отправляет POST /api/control/alpha/switch с CSRF. Operator/Viewer читают данные, но не переключают профили. Gamma имеет только Ascon capability: AES request отвергается HTTP409. Profile eligibility учитывает реальную provisioned capability; все устройства не получают новые возможности автоматически.

Основной показ: Alpha Ascon → AES → Ascon. Beta и Gamma продолжают независимую телеметрию. В UI подтверждение запроса, broker delivery, READY, DEVICE_APPLIED ACK и verified telemetry представлены раздельно. HTTP202 означает durable request. Новый effective устанавливается только по matching authenticated telemetry в PG transaction, а не по ACK или рекомендации.

Control interruption тестирует сохранённый pending request без ложного effective; после restart worker продолжает существующий переход. При неизвестном исходе действуют прежние UNKNOWN_OUTCOME/reconciliation semantics, не автоматический downgrade.

Финальный probe читает исходный signed ACK из Device SQLite ledger read-only, проверяет HMAC и binding к команде, сопоставляет body с PG. PG live_control_acks.sha256 хранит digest canonical BODY, не wire packet: первая версия Stage16 harness ошибочно смешивала их; исправлен только probe. Историческая HMAC проверка делается на timestamp создания сообщения, без заявления, что просроченный ACK допустим сейчас.

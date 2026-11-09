# Каталог профилей

src/policy/profiles.py независим от старой ORM Algorithms.

| profile_id | Алгоритм | Статус | Совместимость |
|---|---|---|---|
| ascon-aead128-v1 | Ascon-AEAD128 | implemented | MQTT telemetry v2, TLS, AEAD; key/nonce/tag16 bytes |

Registry включает version, параметры, capabilities, условия protocol и ограничения.
Reference implementation не объявляется полностью независимо verified или
constant-time. activation_allowed описывает поддержку профиля, а recommendation
всегда applicable=false без device-side управления/ACK. Требуются mqtt_tls, aead,
telemetry_v2; текущий PG реестр устройств допускает только Ascon-AEAD128.

«Магма» и CRISP не зарегистрированы реализованными. Неизвестный ID получает
unsupported_profile. simulated-profile появляется только во временном каталоге
SIMULATION; GET /api/policy показывает исключительно реальный registry.

Для нового реального профиля необходимы реализация/режим/тестовые векторы,
проверенная совместимость формата и capabilities устройств, обоснованные свойства
защиты, согласованное provisioning и самостоятельный защищённый command protocol.
Применение «Магмы» не означает реализацию CRISP. Не задаётся автоматический рейтинг
криптостойкости по названию, длине ключа или номеру риска.

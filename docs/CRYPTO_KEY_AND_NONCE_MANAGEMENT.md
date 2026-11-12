# Ключи, nonce и anti-rollback

Fresh scripts.prepare_control генерирует CSPRNG-независимые значения на device:
Ascon128, AES128, controller→device HMAC256, device→controller HMAC256. Shared key
между устройствами/профилями/направлениями запрещён loader. Provisioned secrets —
локальные 0700/0600; в PG только fingerprints/key references/capabilities. Web не
получает control keys; Docker image не содержит секретных файлов. Передача ключей
по MQTT/удалённое распределение НЕ реализованы. В текущей provisioning версии
числа command epoch и telemetry key epoch совпадают, но storage/counters/replay
namespaces полностью отдельны. Независимая ротация требует reviewed provisioning.

AES nonce = key_epoch unsigned32 big endian || sequence unsigned64 big endian,
ровно 96 bits, tag128 bits. Общий telemetry sequence между Ascon/AES; Ascon старые
packets сохраняют случайный 16 byte nonce. На новый process boot agent посылает
свежий UUID challenge. PG атомарно резервирует следующий диапазон 10000 sequence
выше ВСЕХ ранее выданных диапазонов и receiver high-water mark, прежде чем worker
может отправить authenticated grant. Agent принимает только текущий request/boot,
фиксирует локальный reservation high-water, не восстанавливает range cursor из
state-файла. На restart остаток диапазона теряется, следующий диапазон новый.

Crash до publish/возврат к прежнему AEAD/повтор команды не возвращают sequence.
MQTT QoS1 retry использует сохранённый ciphertext payload Paho, не encrypt повторно.
Локально восстановленный старый state получает новый диапазон; устаревший профиль/
command ledger блокируется сверкой с сервером. Утрата state блокирует startup.
Повтор диапазона от rollback server обнаруживается локальным reservation watermark.
Лимит выдачи 2^32-1 на epoch; дальше требуются новые keys/epoch, не wrap-around.

Trust boundary: PG durable authority и свежий process boot. Одновременный rollback
ВСЕХ PG/device копий/работающей VM с прежними ключами не решается программным
счётчиком; запрещён, требуется новая epoch/key material. Не заявляется hardware
anti-rollback. Неограниченная offline работа после исчерпания range не обещается.
Control HMAC не имеет encryption nonce; anti-replay обеспечивается отдельным
command epoch/sequence/UUID/digest ledger, не telemetry replay-state.

## Stage11: MGM authority

Новый независимый256-bit telemetry key каждого device/profile/epoch. ICN=`epoch32BE || sequence64BE || 4c434d01`, MSB0; строгие пределы без truncation/modulo. Migration0010 добавляет per-key usage/reservation ledger, без backfill старого неизвестного использования. Grant целиком сгорает, рестарт запрашивает новый диапазон. Verification allowance расходуется до AEAD отдельным commit, без превращения PG outage в invalid packet. Исчерпание/потеря authority → fail closed/reviewed rekey. Для MGM-capable устройства обнаруженный PG rollback блокирует authority durable; совместный откат всех authorities требует новых ключей/эпохи. [Полное обоснование](KUZNYECHIK_NONCE_AND_KEY_BUDGET.md).

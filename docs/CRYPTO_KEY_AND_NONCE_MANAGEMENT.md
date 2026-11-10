# Ключи, nonce и anti-rollback

Fresh scripts.prepare_control генерирует CSPRNG-независимые значения на device:
Ascon128, AES128, controller→device HMAC256, device→controller HMAC256. Shared key
между устройствами/профилями/направлениями запрещён loader. Provisioned secrets —
локальные0700/0600; в PG только fingerprints/key references/capabilities. Web не
получает control keys; Docker image не содержит секретных файлов. Передача ключей
по MQTT/удалённое распределение НЕ реализованы. В текущей provisioning версии
числа command epoch и telemetry key epoch совпадают, но storage/counters/replay
namespaces полностью отдельны. Независимая ротация требует reviewed provisioning.

AES nonce = key_epoch unsigned32 big endian || sequence unsigned64 big endian,
ровно96bits, tag128bits. Общий telemetry sequence между Ascon/AES; Ascon старые
packets сохраняют случайный16byte nonce. На новый process boot agent посылает
свежий UUID challenge. PG атомарно резервирует следующий диапазон10000 sequence
выше ВСЕХ ранее выданных диапазонов и receiver high-water mark, прежде чем worker
может отправить authenticated grant. Agent принимает только текущий request/boot,
фиксирует локальный reservation high-water, не восстанавливает range cursor из
state-файла. На restart остаток диапазона теряется, следующий диапазон новый.

Crash до publish/возврат к прежнему AEAD/повтор команды не возвращают sequence.
MQTT QoS1 retry использует сохранённый ciphertext payload Paho, не encrypt повторно.
Локально восстановленный старый state получает новый диапазон; устаревший профиль/
command ledger блокируется сверкой с сервером. Утрата state блокирует startup.
Повтор диапазона от rollback server обнаруживается локальным reservation watermark.
Лимит выдачи2^32-1 на epoch; дальше требуются новые keys/epoch, не wrap-around.

Trust boundary: PG durable authority и свежий process boot. Одновременный rollback
ВСЕХ PG/device копий/работающей VM с прежними ключами не решается программным
счётчиком; запрещён, требуется новая epoch/key material. Не заявляется hardware
anti-rollback. Неограниченная offline работа после исчерпания range не обещается.
Control HMAC не имеет encryption nonce; anti-replay обеспечивается отдельным
command epoch/sequence/UUID/digest ledger, не telemetry replay-state.

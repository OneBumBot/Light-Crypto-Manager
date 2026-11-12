# Российские AEAD: технический проект, Stage 10

Статус: **design only**. Ни один новый профиль не зарегистрирован для live activation. Реальные реализации, Python binding, ARM, независимая проверка и E2E относятся к этапу11. ГОСТ-реализация не означает сертификацию продукта; выводы о регуляторном соответствии здесь не делаются.

| Критерий | Kuznyechik-MGM | Magma-MGM |
|---|---|---|
| Предварительный ID | kuznyechik-mgm-v1 | magma-mgm-v1 |
| Спецификация cipher | ГОСТ Р34.12-2015; [RFC7801](https://www.rfc-editor.org/rfc/rfc7801) | ГОСТ Р34.12-2015; [RFC8891](https://www.rfc-editor.org/rfc/rfc8891) |
| Block / key | 128 / 256 бит | 64 / 256 бит |
| AEAD | MGM, [RFC9058](https://www.rfc-editor.org/rfc/rfc9058) | MGM, тот же RFC, иные bounds |
| Tag proposal | полный128 бит | полный64 бита; сниженная integrity margin |
| Independent KAT | RFC7801 + RFC9058 AppendixA.1 | RFC8891 + RFC9058 AppendixA.2 |
| Python / ARM | binding/build/ABI ещё не проверены | не проверены |
| Research suitability | кандидат для первого proof-of-concept | только после отдельного usage-budget решения |

MGM: ICN имеет n−1 бит и уникален под ключом. Длины AAD и plaintext ограничены; их суммарная битовая длина строго между0 и2^(n/2). Оба пустыми быть не могут. Tag фиксируется протоколом, 32..n бит. Authentication проверяется перед выдачей plaintext; failure не меняет replay/effective. Эти требования и bounds ниже взяты из RFC9058 §§4,6; RFC Informational, не IETF Standards Track.

## Usage budget: расчёт, не обещание безопасности

В модели RFC9058: CA≤3(s+4q)^2/2^n; IA≤3(s+4q+l+3)^2/2^n+2/2^S. q — encrypt queries, s — суммарные блоки AAD/plaintext, l — длина подделки. Для многократных попыток/многих ключей требуется отдельный aggregate analysis. Это не максимальные объёмы, гарантированные самим размером счётчика.

Наш пример **вывода из формулы**, не утверждённый профиль: при консервативных 1024B AAD+4096B plaintext на invocation s/q≤640 для n64; для цели CA≤2^-32 получаем q≤floor(sqrt(2^32/3)/644)=58. Для n128 s/q≤320 и q≤floor(sqrt(2^96/3)/324)≈5.0×10^11. Integrity/forgery reserve дополнительно уменьшит budget. Реальные software payload меньше, но нельзя принимать их размер за гарантированный верхний предел. Поэтому нынешний grant10000 совершенно не является приемлемым Magma budget по умолчанию. Для Magma 63-bit уникальность не решает 64-bit block collision bounds. До утверждения threat model/epsilon/попыток/объёма **activation запрещена**. Консервативный лимит должен действовать и на ошибочные authentication attempts.

## Nonce/key strategy requirements

Не переносить `epoch32||seq64` AES-GCM. Для Kuznyechik исследовать байтовое представление `0 || epoch31 || seq64 || domain32` (128 bits, значимый ICN127). Domain фиксирован профилем/направлением, не случайная замена uniqueness. Это предложение, а не внедрение; формально доказать инъективность, big-endian, диапазоны и отсутствие MSB1. Отдельный новый случайный256-bit key для каждой device/profile/epoch/direction; никаких HKDF по собственному проекту без отдельного решения.

Для Magma старый состав полей не помещается. Возможный путь исследования: ключ уникален для эпохи, ICN63=строго монотонный per-key counter, MSB0 в8B. Требуются новые profile-specific accounting, крайне малые block/invocation budgets и ротация до исчерпания; не усекать existingsequence и не применять modulo. Потеря ledger → остановка и новые ключи/эпоха по контролируемому recovery, не reset. В MQTT QoS1 повторяются **те же ciphertext bytes**, AEAD заново не вызывается; сервер unique identity/replay admission сохраняется.

## Проверенные источники реализаций (2026-11-12)

| Кандидат | Что подтверждено исходниками | Лицензия / интеграция | Что неизвестно / решение |
|---|---|---|---|
| [drobotun/gostcrypto](https://github.com/drobotun/gostcrypto) | Python Kuznyechik/Magma; `gost_34_13_2015.py`: ECB,CBC,CFB,OFB,CTR,MAC; MGM в данном API отсутствует | [MIT](https://github.com/drobotun/gostcrypto/blob/master/LICENSE); Python, Docker возможен | Не готовый AEAD provider. ARM throughput, constant-time и независимый audit не проверены. Не составлять CTR+MAC самовольно |
| [tarantool/go-gostcrypto](https://github.com/tarantool/go-gostcrypto) | pure-Go primitives и `mgm/mgm.go` для64/128, AEAD Open; одно значение MGM не goroutine-safe | [BSD2-Clause](https://github.com/tarantool/go-gostcrypto/blob/master/LICENSE); нужен ограниченный binding/отдельный native adapter | Python API отсутствует; ARM сборка и KAT здесь не запускались; есть [RFC KAT source](https://github.com/tarantool/go-gostcrypto/blob/master/mgm/mgm_test.go), но он здесь не исполнялся; активное состояние репозитория не равно аудиту |
| [gost-engine/engine](https://github.com/gost-engine/engine) | reference GOST implementation для OpenSSL | [Apache2.0](https://github.com/gost-engine/engine/blob/master/LICENSE); reproducible build надо подтвердить на pinned revision; требуется EVP binding | Наличие cipher не доказывает MGM AEAD API. Не предполагаем совместимость `cryptography.AESGCM` с произвольным EVP provider |
| PyGOST / GoGOST upstream | upstream недоступен через доступный web tool в этом исследовании | **not_verified** | Не выбирать fork по названию/PyPI; проверить upstream, лицензию, MGM/KAT, поддержку до решения |

Ни один кандидат не установлен в runtime и не выбран production-ready. Для всех: pinned source commit+hash, лицензия dependencies, CVE/release history и reproducible Docker x86_64/aarch64 builds, Python buffer ownership/zeroization limitations, constant-time review, independent vectors, malformed/tag tests, performance на ARM. Python/Go GC не гарантирует уничтожение всех копий ключа. Не передавать секреты в command-line/IPC logs; binding должен получать bytes через ограниченный API, не stdout.

## Registry/provider contract

Существующий `src/crypto_profiles.py` остаётся authority только двух реализованных профилей. Будущий immutable descriptor: profile_id,algorithm,aead_mode,key_bytes,nonce_bytes,tag_bytes,profile_version,protocol_version,aad_compatibility,key_reference_schema,nonce_policy_id,invocation_and_block_limits,device_implementations,receiver_implementation,kat_evidence,activation_eligibility,limitations. Draft descriptors держать отдельно от PROFILES/IMPLEMENTED и UI selectable options.

Будущий provider `validate_parameters(key,nonce,aad,plaintext_or_ciphertext)` → точный ValueError/InvalidTelemetry на внешней границе; `encrypt`/`decrypt` one-shot, ciphertext||tag; `validate_usage_limits(accounting)` в durable transaction до nonce выдачи. Provider не выбирает ключи, не управляет policy, не делает fallback. Dispatch только по проверенному profile, keyreference и AAD binding. Usage reservation атомарна; crash сжигает grant. Не рефакторить работающий Ascon/AES ради абстракции до независимых KAT.

## Совместимость telemetry/control/storage

Telemetryv2 уже содержит algorithm, nonce(base64),ciphertext||tag,AAD profile/device/topic/epoch/sequence. Для Kuz16B nonce/tag и32B key **контейнер структуры вероятно достаточен**, но текущие registry validator/dispatch/provisioning/SQL supported profiles/Mongo enum/UI options фиксируют две реализации. Это места будущего аддитивного изменения, а не разрешение просто вписать название. Magma8B tag потребует убрать только доказанно profile-specific hardcoded16B checks с тестами и лимитами, не ослабить общий decoder. MQTT8192B/packet12288B сохраняются. Любое изменение wire семантики потребует version/migration plan; не изменять AAD каноникализацию молча.

Provisioning: независимый key32B/profile/epoch, capabilities только с подтверждённым provider; Agent и receiver должны реализовать одинаковые test vectors. PG: аддитивная migration для profile metadata/usage reservation, если существующей схемы недостаточно; старые migrations/replay/commands не reset. Mongo: расширить разрешённый crypto_profile только после release gate, existing historicalvalidator/data сохранить. Control HMAC format, command sequence, PREPARE/ACTIVATE, expiry/grace, keyreference binding и telemetry receipt сохраняются. Новая implementation не получает automaticactivation. UI данные берёт из реализованного registry; никаких selectable drafts.

Release gate: independent block+MGM KAT; both implementations/device+receiver; key separation; nonce uniqueness/limits; AAD/tag failures; restart/crash/lease exhaustion; bidirectional realTLS switch; lostACK/PG recovery; receipt-only effective; старые Ascon/AES regression; bounded perf/ARM. До выполнения всех условий activation_allowed=false. Этап10 архитектурно определяет необходимые изменения, не утверждает готовность production.

При утверждении будущих wire names использовать однозначное AEAD имя (`Kuznyechik-MGM` / `Magma-MGM` как предложения), а не только название блочного cipher. ГОСТ28147-89 с произвольным S-box не считать взаимозаменяемым с Magma RFC8891: проверить подстановки, endian и каждый intermediate/block/MGM vector. Алгоритм outer/AAD/keyreference и profile_id control должны иметь единственное согласованное отображение. Типы/размеры внешнего JSON проверять до hash lookup и numeric conversion; будущие профили обязаны сохранить poison-message availability tests.

### Особое ограничение текущего lease/control контракта

Существующий lease выдаёт диапазон10000 sequence для device, а не отдельный block/invocation budget каждого будущего key reference. Sequence high-water не равен количеству вызовов конкретного AEAD: при переключении первый Magma sequence может быть30001, хотя этот ключ ещё не использовался. Нельзя считать max_sequence budget или разрешить старый grant на10000 новых Magma encryptions.

Для Kuznyechik текущий общий предел2^32−1 ниже иллюстративного confidentiality budget при указанных worst-case payload; это **не** закрывает aggregate integrity/forgery attempts и key rotation. Для Magma потребуется отдельное durable per-key usage reservation до первого encryption, включая сожжённые неиспользованные grants. Если budget должен передаваться устройству, текущая strict lease schema не допускает произвольных дополнительных полей: нужна явно спроектированная versioned migration control/lease, совместимая с HMAC/device-topic/replay/старым состоянием. Сохранение базового HMAC и PREPARE/ACTIVATE не означает, что wire protocol можно расширить без версии. Это отдельный gate этапа11; Stage10 ничего в lease protocol не меняет. Возможность Magma live integration пока **не обоснована**.

### Конкретные dispatch/version препятствия

Текущий encrypt/decrypt содержит `if AES ... else Ascon`: это корректно только пока PROFILES содержит **ровно две** действующие реализации. Простое добавление третьего descriptor попадёт в Ascon branch. Это внутреннее ограничение будущего расширения, не подтверждённая уязвимость текущего сетевого пути: неизвестные wire names уже отклоняются. На этапе11 заменить dispatch явным provider mapping и fail-closed unknown handler **до** регистрации нового профиля, не пробовать несколько decrypt/key вариантов.

BY_ALGORITHM требует инъективного отображения: одинаковое algorithm wire name для двух profile versions сейчас затрёт mapping. Версия будущего AEAD должна иметь однозначный wire identifier либо обоснованную protocol migration; display label не должен определять криптографические параметры. Проверить duplicate IDs/names при регистрации. Структура telemetryv2 сама по себе этого release gate не обеспечивает. Registry validator сейчас допускает только согласованный Ascon legacy key_hex/AES telemetry_keys;32B ГОСТ key не может появиться простым изменением длины AES key.

## Дополнение Stage11

Предыдущие разделы фиксируют design этапа10. Kuznyechik-MGM теперь реализован через pinned tarantool Go provider и проверен на software lab: [implementation](KUZNYECHIK_MGM_IMPLEMENTATION.md). Для новой версии используются key32B, full tag16B, ICN epoch31/sequence64/domain32 и отдельная durable usage authority, без изменения telemetryv2/HMAC wire. Допуск ограничен явно авторизованным Stage11 namespace, не глобальным production activation. Magma остаётся design-only: новый 64-bit budget/nonce анализ, independent KAT, provider/recovery validation всё ещё обязательны; реализация не начата.

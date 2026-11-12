# MGM ICN и бюджет ключа

Профиль `kuznyechik-mgm-v1`, wire `Kuznyechik-MGM`, key32B, ICN16B, tag16B. Направление только device→receiver. Для каждого device/profile/epoch новый независимый случайный ключ; command/status HMAC и Ascon/AES не переиспользуются.

## Инъективное кодирование

`epoch32_BE || sequence64_BE || 4c434d01`, где `1≤epoch≤2^31−1`, `1≤sequence≤2^63−1`. Это ровно `0 | epoch31 | sequence64 | domain32`, старший бит равен0, домен фиксирован `LCM\x01`. Равенство ICN означает равенство первых4 и следующих8 байтов; фиксированная ширина big-endian однозначно восстанавливает оба целых. Следовательно, разные допустимые пары не совпадают. Никакого modulo, усечения или wraparound. Receiver проверяет **точное** соответствие nonce аутентифицируемым координатам до provider. Разные устройства имеют разные ключи; cross-key nonce collision не является reuse под одним ключом.

Практический grant сохраняет прежний предел общего device sequence `2^32−1` и размер10000. После restart выдаётся новый диапазон строго выше durable high-water; непотраченный хвост сгорает. После перехода на другой профиль и обратно глобальный sequence продолжает расти. QoS1 повторяет прежний ciphertext, не вызывает encode/encrypt повторно.

## Консервативный per-key budget

Верхние размеры provider: AAD1024B, plaintext4096B, сумма положительна и значительно меньше ограничения RFC9058. `ceil(AAD/16)+ceil(P/16)≤320` блоков на invocation. Telemetry envelope дополнительно ограничивает ciphertext4096B, packet8192B. В расчёте оставлен больший консервативный provider предел.

- q≤2^20 зарезервированных encryption invocations;
- s≤320×2^20 блоков;
- f≤2^20 verification attempts (включая корректные, invalid tag и replay);
- l≤320 блоков на одну попытку;
- S=n=128.

По [RFC9058 §6](https://www.rfc-editor.org/rfc/rfc9058#section-6), CA≤3(s+4q)^2/2^128; IA одной попытки≤3(s+4q+l+3)^2/2^128+2/2^128. Получаем CA≈2^-69.7; консервативный union bound по f попыткам ≈2^-49.7 на ключ. Это запас относительно **per-key цели 2^-48**, в модели анализа RFC. Для двух свежих лабораторных ключей aggregate bound≈2^-48.7. Это расчёт с ideal-cipher assumptions, не доказательство устойчивости данной реализации к timing/host compromise. Для иного количества ключей/параметров нужен новый aggregate анализ.

## Атомарное резервирование

Аддитивная migration0010 после0009 создаёт `crypto_key_usage` и `crypto_usage_reservations`. Secrets отсутствуют. Fresh initialization допускается только вместе с **новой** live-control identity. Старые/неизвестные использования не backfill нулями. Key reference связан с device/epoch/profile и fingerprint приватной конфигурации.

Каждый boot grant для устройства с MGM key резервирует потенциальное использование **всего диапазона** под этим ключом, даже пока работает Ascon/AES. Это намеренный консервативный расход, а не подсчёт MGM вызовов из max_sequence. HMAC lease wire schema не меняется. SQLite/agent используют только подписанный диапазон, новый процесс никогда его не восстанавливает для повторного encryption.

Device row lock + per-key row lock; сумма reservation ledger проверяется против counter. Usage increment, reservation, nonce lease и server high-water commit в одной транзакции. Exact request retry возвращает тот же grant без дополнительного расхода. Неиспользованные, но committed reservations не возвращаются. При нехватке следующего grant отказ с требованием reviewed rekey; дробный остаток не расширяет лимит. Бюджет и SQL CHECK bounded; concurrency проверяется двумя параллельными issuer.

До каждого MGM decrypt отдельная транзакция фиксирует verification attempt. Tag failure не возвращает allowance. Отказ PostgreSQL здесь остаётся инфраструктурной ошибкой: manual ACK не выдаётся, redelivery сохраняется. Неверный tag не меняет replay high-water, Outbox, effective receipt, device security identity. Сам verification counter меняется намеренно.

## Восстановление

- Нет SQLite: agent не создаёт новую БД со старыми ключами; fail closed.
- Stale SQLite при актуальном PG: новая boot reservation, старый range не используется; command floor/profile проверяются.
- Откат PG range ниже SQLite high-water: для MGM-capable agent durable блокировка authority, сохраняющаяся после restart; только reviewed recovery/rekey, reset API отсутствует.
- Удалён/повреждён usage ledger: отказ, не автоматическая инициализация.
- Одновременный откат PG **и** SQLite до согласованного старого snapshot принципиально не обнаруживается без внешнего monotonic anchor. После такого восстановления нельзя запускать старые ключи: новые независимые ключи и эпоха, reviewed provisioning/recovery. Не заявляем защиту от произвольного административного rollback всех authorities.
- Исчерпан q/s/f: прекратить выдачу/проверку под старым ключом; alert оператору через отказ/аудит. Новые ключи/эпоха требуют отдельной reviewed процедуры, не сброса counters.

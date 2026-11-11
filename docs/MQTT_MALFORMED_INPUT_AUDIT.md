# Аудит границ недоверенного ввода — 8-fix

Baseline: `67eb3bcff937c2b0975b18444680e98af84e76fd`, чистая исходная ветка
`feature/adaptive-crypto-control`; исправления — `feature/adaptive-crypto-control-fix`.
Сетевой JSON может содержать любой JSON-тип; TLS/ACL не делают его доверенным.
Список тестов и фактических запусков: [STAGE8_FIX_RESULTS.md](STAGE8_FIX_RESULTS.md).

| Модуль / операция | Источник и установленные ограничения | Вывод |
|---|---|---|
| telemetry.decode_packet, outer profile → BY_ALGORITHM | MQTT JSON, ранее поиск до проверки типа | Подтверждён TypeError для list/dict; добавлен exact str перед lookup |
| telemetry packet schema | strict_json + exact dict/fields; int schema=2, размер 8192 | null/array, missing/extra/duplicate keys отвергаются InvalidTelemetry |
| nonce/ciphertext/associated_data | exact str, bounded strict base64; длины профиля/tag/AAD | Нет lookup по неподтверждённому типу; malformed types отвергаются |
| AAD device_id → registry | exact str + ASCII regex до membership | list/object не попадают в lookup; неизвестное устройство отвергается |
| AAD topic/profile | сравнение с доверенными строками registry/MQTT/outer | Equality безопасно для всех JSON-типов; неверный тип не может пройти binding |
| key_epoch/sequence_number → to_bytes, SQL | exact int (bool запрещён), 1..2^31−1 / 1..2^63−1 до операции | Нет OverflowError от внешнего numeric; AES nonce проверяется до decrypt |
| sensor numeric/timestamp | int/float, bounds до isfinite; UTC bounded str, controlled date errors | Огромные числа отвергаются до float conversion; finite/ranges обязательны |
| crypto_profiles.encrypt/decrypt → PROFILES | В receiver profile получен из проверенного BY_ALGORITHM | Прямые вызовы с list могут дать TypeError/KeyError, но это внутренний API, не сетевой путь |
| encode_packet / validate_registry / load_registry | Локальный producer и приватный provisioning file; path из env/аргумента | Не сетевой API; конфигурация считается операторской. Некоторые неверные Python-типы прямого вызова могут дать TypeError; не объявлены сетевой уязвимостью |
| ingestion.process_packet | Сначала decode, затем require_enabled/authorize, replay, outbox, observe в одной PG transaction | InvalidTelemetry не поглощает SQL errors. Ни malformed, ни failed transaction не дают admission/evidence |
| receiver.on_message | QoS1 bytes/topic от Paho; incoming отдельно, reject audit separately committed | InvalidTelemetry → rejected без identity, затем manual ACK; unexpected/PG error → disconnect, без ACK. Широкий catch сохраняет инфраструктурную recovery-семантику |
| protocol uid/device/topic | exact str перед UUID/regex; transport topic сравнивается с bound string | Неверные JSON-типы дают ValueError, не ключ/путь |
| protocol requested_profile/local_profile | exact str до PROFILES membership | Защита уже присутствовала; authenticated negative tests добавлены |
| command_epoch/sequence/floor/leases | positive exact int + bounds; command_floor exact int >=0 | До SQLite/PG и .to_bytes тип установлен. floor без верхней границы только сравнивается; не SQL integer argument |
| command_id/correlation_id/transition_id | canonical UUID exact str, затем bound SQL parameters | Непроверенный list/object не достигает ledger lookup |
| key_reference / MAC / SHA256 | exact str; reference равен profile:epoch; hex regex до compare_digest | Unicode MAC и malformed types контролируемо отвергаются |
| phase/result/kind/lease effective/pending | Equality/list membership, не set/dict; выбранные ветки exact schema | Unhashable JSON безопасно отвергается; не используется как dict key |
| agent | bounded queue, open_message → validate → kind dispatch → state.execute | Невалидная команда не меняет SQLite. Файловые пути только env/operator, не command fields |
| state | validate до command_sequence/IDs/SQL; cached ledger проверен на digest; transactions rollback | Прямой execute с валидным body другого kind — внутреннее нарушение API; agent туда его не передаёт |
| worker | topic выбирает device из локального config, затем open_message и SQL transaction | Нет lookup по body device до validate. PG outage обрабатывается как unavailable, не InvalidTelemetry |
| server | request_switch проверяет str до IMPLEMENTED.get/PROFILES; authorize/observe получают VerifiedTelemetry | ACK не устанавливает effective; profile lookup здесь внутренний после AEAD. grant/handle_ack вызываются worker только после validate |
| config | приватный файл 0600, registry, независимые keys, capabilities list из известных строк, epoch | Это локальная trusted boundary, не MQTT. List membership не hash lookup; invalid config прекращает startup. Пути из env, не пакетов |

Изменение runtime минимально: только проверка outer profile. Новых широких
except/нормализации ошибок не добавлено. Наборы Python dict, переданные напрямую
в parser/encoder, и повреждённые операторские файлы не приравнены к MQTT bytes.
Не доказаны дополнительные сетевые TypeError/KeyError/AttributeError/OverflowError
в перечисленных управляющих путях. Это целевой аудит и negative tests, не
доказательство отсутствия любых ошибок и не внешний pentest.

Покрытие различает уровни: parser exact exception types; SQLite ledger side effects;
PG admission/evidence snapshots; реальные TLS/MQTT observations и Mongo delivery;
callback commit failure и реальные PG outage recovery. Замоканный decrypt в отдельном
profile binding test проверяет порядок проверки до crypto; реальные tamper/tag tests
проверяют криптографический отказ независимо от этого теста.

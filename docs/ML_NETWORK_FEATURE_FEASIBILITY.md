# Признаки Network IDS и MQTT/TLS

Единица нового контракта — **TCP packet**, не MQTT payload, flow или sensor sample.
Новая схема tcp-packet-passive-v1 отдельна от network-core-v1. Она использует
5 numeric полей: frame.len, tcp.len, tcp.flags, tcp.window_size_value, tcp.time_delta.
Порядок фиксирован в src/classifier/research/schema.py. Модель пока offline.

| Dataset feature | Extractor / единица | Доступность при TLS | Ограничения |
|---|---|---|---|
| MQTTset frame.len | tshark frame.len; длина packet | Видима пассивному observer | Зависит от link layer, MTU и segmentation; IP len не эквивалентен |
| MQTTset/Edge tcp.len | tshark TCP payload bytes | Видима как длина ciphertext/records | TLS меняет распределение размеров; не plaintext MQTT length |
| MQTTset/Edge tcp.flags | TCP header bitmask, hex→integer | Видим | Retransmission/stack/scenario artifacts возможны; не identity |
| MQTTset tcp.window_size_value | Raw TCP advertised window | Видим | Window scaling отдельно; не путать со scaled window/bytes in flight |
| MQTTset tcp.time_delta | Межпакетный интервал в TCP stream, прошлый packet | Видим при корректной полной capture | Точка наблюдения/packet loss/reordering влияют; не global frame delta |
| MQTTset/Edge mqtt.len/msgtype/qos/topic/payload/conflags | MQTT dissector на открытом трафике | Пассивно **не видны** внутри TLS | Только offline plaintext research либо доверенная broker instrumentation |
| MQTT-IoT-IDS2020 ip len/ttl/TCP flag fields | Packet extractor из статьи | Header поля потенциально видимы | Native CSV не имеет гарантированно frame.len/tcp.len/window/delta; прямого адаптера без raw re-extraction нет |
| MQTT-IoT-IDS2020 num_pkts/bytes/mean_iat | Uni/bidirectional flow | Потенциально вычислимы под TLS | Это другая гранулярность и schema; нельзя считать packet rows |
| Edge tcp.seq/ack/checksum, udp.stream | Протокольные/идентифицирующие поля | Частично видимы | Sequence/checksum/stream IDs могут отражать capture provenance; не используются в новом X |
| Mosquitto auth/ACL status / connection rate | Будущий trusted broker event adapter | Broker знает после TLS termination | Нужны проверенная версия, controller identity и связь с authenticated principal |
| Temperature/humidity после Ascon AEAD | Existing telemetry pipeline | Доступны серверу после проверки | Это Telemetry Anomaly Detection, не замена сетевых признаков |
| Неаутентифицированный device_id / IP | Непроверенное сообщение/заголовок | Может быть видим | Не доказательство устройства; не связывать риск с claimed device_id |

Числа finite, неотрицательные; flags/window/length integral, диапазоны заданы.
Missing whole column → отказ. Missing value → train-only median/missing indicator;
полностью missing training column → отказ. Никаких неизвестных колонок с нулями.
Labels, capture/session IDs, IP/ports, packet number, timestamp, source и credentials
не включаются в predictive X. Timestamp/session нужны для provenance/grouping.

## Статус runtime

Текущий publisher/receiver не создаёт такую packet feature vector. Наличие
теоретически наблюдаемых полей не означает готового collector или качества на TLS.
Новые артефакты загружаются только в offline research; Policy Signal allowlist и
telemetry worker не расширены для live Network IDS. Старые network-core-v1 модели
не могут обработать новую таблицу без отсутствующих28 полей; нулями их не заполняем.

## Технический проект будущего collector

Отдельный серверный read-only компонент, вне MQTT callback/ML telemetry worker.
Только согласованный packet header export либо trusted broker metrics; без
отключения TLS, доступа к telemetry/control keys и автоматической установки
перехватывающего ПО. Для PCAP исследований допустим локальный tshark -r экспорт
точных RAW fields, с зафиксированной версией, link type, clock и capture hash.
Идентичность источника и показатели потерь обязательны. Активные connections,
очередь и временные окна должны иметь пределы/expiry/backpressure.

Offline interface: research.inference.predict(manifest,pipeline,frame,version,
granularity='packet') → offline-network-risk-v1, model/version, model-specific
score/range/direction, threshold, optional predicted type, trusted_detector=false,
binding=unattributed. Это не live Policy Signal; device mapping требует отдельного
проверенного адаптера. p95/p99/throughput нужно измерить на реальном TLS трафике
и целевом сервере; Raspberry Pi/ARM64 пригодность не подтверждена.

Граница покрытия: новая схема принимает только TCP (ip.proto=6). UDP/ICMP rows
исключаются с отдельным non_tcp_excluded counter; их атаки не считаются обнаруженными
или успешно проверенными. Это не универсальный IDS всех IoT протоколов. Для них
потребуются отдельный контракт/данные и оценка; old ICMP/UDP failures не «исправлены».

TCP соединение publisher→broker отличается от broker→receiver. Paho MQTT message
не содержит исходные TCP length/window/timing publisher: наблюдение subscriber
соединения не может подменить client-side/broker-ingress collector.

## Проверено на стенде 7.5b

Добавлен opt-in **исследовательский**, не online IDS collector. Он разделяет
network namespace с virtual publishers и собирает их исходные MQTT/TLS TCP
соединения к отдельному broker; broker→receiver не подменяет этот capture point.
Оффлайн tshark сохраняет5полей tcp-packet-passive-v1. TLS/Ascon не отключались,
MQTT payload/topic/credentials не расшифровываются. Направления/IP/ports/stream IDs
нужны только для ground truth, не для predictive features.

59valid captures/46395packets; first tcp.time_delta0 — штатная семантика tshark,
не заменённое missing значение. Один capture с отрицательной delta изолирован,
схема не ослаблялась. Linktype Ethernet1/IPv4/x86_64 Docker host проверены;
ARM/IPv6/другие capture tools/физические устройства не проверены.

Стенд не стал доверенным network feature collector действующего Policy Worker.
Нет новых fitted Network models/online IDS. Batch/host/kernel и короткие
rejected connections остаются potential shortcuts. External MQTT_UAD header
не содержит4из5требуемых полей; MQTTEEB-D raw header ещё не проверен; IoT-SFC
смешивает Zeek logs. Подробности в EXTERNAL_DATASET_AUDIT_75B.md.

# Дополнение7.5: tcp-packet-passive-v1 (offline)

Отдельная новая schema, старая network-core-v1 ниже не меняется. Порядок5 numeric
features: frame.len, tcp.len, tcp.flags, tcp.window_size_value, tcp.time_delta.
Гранулярность packet, не flow/window/measurement. Диапазоны и hex flags conversion
в research/schema.py; отсутствующая колонка и all-missing train feature отклоняются.
NaN value обрабатывается train-only median+missing indicator; Infinity/invalid types
отклоняются. Metadata source/capture/session/packet/timestamp/labels не входят в X.

Source provenance обязательна; dataset_family задаёт независимую type ontology:
MQTTset6 классов, MQTT-IoT-IDS20205 классов. Binary0=Normal,1=attack. Неизвестные
типы не склеиваются автоматически; тип unseen в RF train отмечается в оценке.
Packet_audited требует отдельный per-packet binary label_column, иначе только
явно обозначенные capture-scenario labels. Режим prepared schema/hash фиксируется.

Offline output contract offline-network-risk-v1 содержит detector=network_ids,
version/model/score/threshold/direction/range, optional type, mode и
trusted_detector=false, binding=unattributed. Он **не является** live Policy Signal
и не создаёт authenticated device identity. Policy allowlist не расширена.

Экстракция/наблюдаемость под TLS и ограничения byte semantics —
ML_NETWORK_FEATURE_FEASIBILITY.md. Поля теоретически наблюдаемы, но действующего
collector в LightCrypto Manager ещё нет; plaintext→TLS переносимость не проверена.
Артефакт loader поддерживает этот явно версионированный offline contract; никакого
неявного zero padding старой30-column schema или отключения TLS нет.

---

# Версионированные признаки и сигнал

## Network IDS: network-core-v1

30 входных колонок:27 numeric +3 categorical, в явном порядке schema.py.
Числовые: arp.opcode/hw.size; icmp.checksum/seq_le; http.content_length/response;
tcp.ack/ack_raw/checksum/connection.fin/connection.rst/connection.syn/
connection.synack/flags/flags.ack/len/seq; udp.stream/time_delta;
mqtt.conflag.cleansess/conflags/hdrflags/len/msgtype/proto_len/topic_len/ver.
Категориальные: http.request.method, http.referer, http.request.version.

- Missing whole column → explicit error. Extra metadata/targets не входят в X.
- Numeric finite/nonnegative; missing NaN допускается только как missing→train
  median imputation. Boolean objects вместо чисел отвергаются; числовые flags0/1.
  Полные field limits в schema.py: checksums16bit, seq/ack32bit, TCP len16bit,
  MQTT flags8bit/type0..15/version0..5, delta0..86400s и др.
- Categories: bounded4096 chars, no control chars; missing→constant imputer;
  protocol-absent numeric0/string0/0.0 → единый __ABSENT__ token. Unknown categories
  разрешены OneHotEncoder(handle_unknown=ignore), max_categories64.
- Imputer/scaler/encoder fitted только train (IF — только normal train). Модель
  сериализуется вместе с ними, feature order и version фиксируются manifest.
- Четыре reported proxies (dns.qry.name.len, mqtt.conack.flags, mqtt.protoname,
  mqtt.topic) не входят в core. Неоднозначные DNS fields текущей копии также не
  используются. Это subset, не доказательство корректности всех extractor fields.

Attack_label и Attack_type валидируются отдельно:0 iff Normal,1 iff other category.
RF multiclass сохраняет string classes внутри estimator; нет LabelEncoder,
подогнанного на test. Normal class должен быть в train. Реальный текущий split
имеет7 train categories, не15; см. ML_EVALUATION.md. Schema несовместимого collector
отвергается, temperature/humidity никогда не подставляются в network fields.

## Telemetry: telemetry-causal-v1

Raw обязательны: device_id, key_epoch, sequence_number, measured_at, received_at,
temperature, humidity. Показания в прежних protocol ranges: -80..150°C,0..100%;
числа конечные, bool не является числом; UTC даты; delay в пределах±86400s.
Секреты/keys/токены не features и не ML event payload.

Source identity — device/epoch/sequence. Accepted sequence задаёт порядок внутри
устройства/эпохи. Только предшествующие sequences участвуют в окне; measured_at и
received_at внутри него должны быть монотонны и не выходить в будущее target.
При некорректных часах/порядке окно не оценивается. Ни centered rolling, ни
backfill из будущих measurements не применяются. Offline output сортируется по
received_at лишь после построения причинных features для temporal partitions.

Window=8 по общей конфигурации (DEMO integration artifact=5), разрешено3..256.
При меньшей истории warmup, без выдуманного baseline. Переход epoch начинает
новое окно. Окно не смешивает разные device IDs. Train-only device baseline:
median и scale=max(1,1.4826*MAD) отдельно для temperature/humidity, минимум3
готовых train окон на устройство. Unseen device → unknown_device, без global fallback.

Порядок11 numeric features:

```text
temperature, humidity, delta_temperature, delta_humidity,
rolling_temperature, rolling_humidity, std_temperature, std_humidity,
interval_seconds, missing_intervals, ingestion_delay_seconds
```

Rolling mean/std (ddof0) только по предыдущимN измерениям, current не включён.
Current/rolling levels центрируются и масштабируются device baseline; deltas/std
делятся на его scale. interval/delay выражены в единицах10s. Missing intervals:
min(1000,max(0,int(interval/expected_interval)-1)); expected_interval фиксирован в
manifest, сейчас общий для данного artifact. Это gap estimate после следующего
сообщения, а не независимый таймер обнаружения молчащего устройства.

Statistical score — max abs нормализованных current/delta/rolling levels и gap
count. Std/time dimensions дополнительно использует IF. Statistical scale0..∞;
IF score=-score_samples,0..1. Большее значение означает большую нетипичность,
не вероятность кибератаки. Threshold обучается/калибруется на validation, не test.
Без достоверных labels quantile означает alert-quantile, не измеренную FPR.

## Policy signal v1

src/ml_signals.signal(event,model) допускает только status=ok и содержит:
identity, detector, model_id/version, feature_version, score, threshold,
is_anomaly, evaluated_at UTC, score_direction=higher_is_more_anomalous,
score_range, score_semantics, mode и trusted_detector=false. Null/unscored
статусы не преобразуются в «норма». Диапазон у разных моделей различен.

Никаких algorithm/profile/key/command полей нет. Сигнал не ослабляет текущую
защиту; правила будущего Policy Engine требуют отдельного этапа. Network future
interface возвращает дополнительно predicted_class; его argmax может отличаться
от отдельного thresholded risk signal, что учитывается раздельно в метриках.

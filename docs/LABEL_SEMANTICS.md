# Семантика исследовательских меток 7.5b-fix

Архив75b-v1 оставлен неизменным. Его `label_scope=packet_audited` был методически
неверен: подтверждалась активность соединения, не вредоносность каждого ACK/TLS
record. Исторический validator теперь воспроизводит старые правила независимо,
но возвращает `historical_rule_reproduction_only`, не scientific verification.
CLI build по умолчанию создаёт v2; `--archive-v1` нужен только для старого rebuild.

Новый контракт: dataset75b-fix-v2.2, rules connection-evidence-v2.2. Пять numeric
features tcp-packet-passive-v1 НЕ изменены. Observation остаётся TCP packet;
единица аннотирования — **connection activity**, для rate/pattern — её временное
окно (`label_scope=window_behavior`). Повторение одной контекстной метки на многих
строках не создаёт независимые attacks. Оценивать позже нужно также connections/
windows/captures; packet-weighted recall нельзя назвать количеством найденных атак.

| Поле | Смысл |
|---|---|
| scenario_category | Намерение orchestrator, не доказательство |
| connection_activity | Заявленная роль конкретного соединения, не весь capture |
| label_unit | connection_activity; не malicious_packet |
| label_scope | connection_activity / window_behavior |
| packet_specific_evidence | none_encrypted_tls — packet_event не установлен |
| ground_truth | normal / controlled_violation / unknown в указанном scope |
| label_confidence | corroborated_activity / unconfirmed |
| label_evidence_level | independent_source_activity / insufficient |
| label_reason | Детерминированное основание/причина abstention |
| authenticated_device | Только MQTT identity после broker auth; это не атрибуция anonymous AEAD reject |

`normal` означает подтверждённую лабораторную normal activity, не доказательство
безопасности всех байтов. `controlled_violation` — контролируемое поведение/отказ
на соединении, не подтверждённая реальная атака. Handshake/boundaries, отсутствие
событий/связи/точной корреляции → unknown. Unknown не преобразуется в0, не попадает
в dataset.csv. Для нерасшифрованного TLS packet-specific maliciousness не установлена.

## Доказательства сценариев

- Normal: exact socket/session +broker auth/authorized publish +timed authenticated
  receiver event. Штатный QoS1 DUP: broker d1 +replay ledger допускаются как normal.
- Wrong credentials: CONNACK5 с broker client ID и endpoint закрытия; identity пустая.
  При нескольких pending connections нельзя выбирать ближайшую по времени.
- ACL: Denied PUBLISH принадлежит именно endpoint/session и её временному интервалу.
  Один client ID из глобального списка и QoS1 PUBACK недостаточны.
- Deliberate replay: authenticated device/epoch/sequence, prior accepted до нового
  соединения, контролируемое повторное действие с тем же digest, broker d0, timed
  PG replay и **независимый keyless MQTT fanout witness** с одинаковым digest до/после.
  AD witness untrusted до корреляции с AEAD-verified PG identity. Это не direct
  signed recipient digest: корреляция предполагает отсутствие конкурирующих
  событий той же identity; неоднозначность/разные hashes → unknown.
- Tampered: local crypto failure/anonymous PG reject не связываются с device.
  Даже при broker digest witness независимого authenticated failure identity нет:
  **unknown**, локальное намерение остаётся diagnostic, не verified_packet_attack.
- Rate/pattern: trusted broker Received PUBLISH events, а не число TCP packets.
  DUP1 исключены, MID deduplicated внутри session. TCP segmentation/retransmission
  и размеры пакетов не являются MQTT PUBLISH rate.

Rate:≥8distinct non-DUP publishes; matched normal peer≥6publishes с median interval
в nominal±jitter±0.05s. Bounded rate:median≤0.75nominal и≥90%intervals внутри
0.5nominal±jitter±0.05s. Pattern:≥3intervals<0.8nominal и≥3>1.2nominal,
≥70%соседних пар чередуются. Только внутри first/last broker publish window,
с20msкраевой неопределённостью и margin часов. Недостаточная история, normal
intervals, отсутствующий observer или неоднозначные границы → unknown.

Это broker-observed MQTT PUBLISH behavior, не точная оценка device emission time,
не частота TCP пакетов и не доказанный DoS. Числа заданы до ML, не подбирались по
RF/IF/test predictions. Формального external preregistration нет; дальнейшая
смена правил требует новой версии. Абсолютный bound Docker log latency не измерен.

## Статус данных

Отдельны real_packet_capture, generated_test_clients, controlled_lab_scenarios,
label_unit/evidence_level, independent_label_verification, external validation,
attack_realism_scope и known_shortcut_risks. Scientific_quality_available больше
не вычисляется из synthetic=false+packet_audited: для текущих источников он false.
Engineering/reconciliation success не означает 100%label accuracy, IDS quality
или переносимость. DEMO/RESEARCH, trusted_detector=false, Policy DRY_RUN сохранены.

V2.2 дополнительно ограничивает activity пересечением локального TLS lifecycle
с независимыми broker opened/closed timestamps. Отсутствующий session end → unknown.
NaN/Infinity/duplicate JSON keys запрещены. Изменение локального closed_at не может
расширить окно за независимо зарегистрированное закрытие. Connection denial может
быть подтверждён без единой уверенно размеченной TCP строки: пакетная плотность
не должна заставлять ослаблять margin ради positive support.

# Этап 8 — реальное ручное переключение AEAD

Ветка feature/adaptive-crypto-control от f6f3c23. Реализовано и проверено настоящее
Ascon-AEAD128↔AES-128-GCM переключение **software IoT device agent**, не AckSimulator.
Это MANUAL_AUTHORIZED_CONTROL; автономное управление по RF/IF не включено.
Policy Worker реально запущен в DRY_RUN, его applied records остаютсяNULL.

## Что реализовано

- crypto_profiles: explicit dispatch двух AEAD, AESGCM из cryptography 50.0.2.
  Ascon reference и его пакеты не переписаны. Telemetry schema 2/5outer fields/
  6AAD fields сохраняются; wire names Ascon-AEAD128/AES-128-GCM.
- Раздельные per-device Ascon128/AES128/command-HMAC256/status-HMAC256 keys.
  Только preprovision,0700/0600, нет plaintext keys в commands/PG/API/images.
- Control v2: canonical JSON+HMAC-SHA-256, domain/topic/direction/device binding,
  strict schema/UUID/TTL/epoch/sequence, protected READY/APPLIED ACK.
  Это MAC, не control encryption; metadata confidentiality обеспечивает TLS.
- Точные MQTT ACL: controller write commands/read status; device только свои
  command/status; никаких command rights у web/receiver/research observer.
  Web создаёт только PG intent. Нет общего анонимного ACL и plaintext fallback.
- Durable PG command outbox, ограниченные retry/claim lease, concurrency per-device.
  Network publish после commit; одинаковые bytes при retry. At-least-once+
  идемпотентный эффект, не end-to-end exactly-once.
- Реальный Device Agent: durable SQLite PREPARE/ACTIVATE/profile/replay/cached ACK,
  process lock, новый nonce range на каждый boot, graceful shutdown.
- Receiver подтверждает effective только после AEAD/AAD/device/topic/profile/epoch/
  replay admission. Replay, anomalies, outbox и effective receipt в одном PG commit.
  ACK/кнопка сами по себе не подтверждают effective.
- Bounded per-device transition grace; после confirmation старый профиль запрещён.
  Потеря ACK не даёт downgrade. UNKNOWN_OUTCOME требует безопасной сверки.
- Flask/control: admin RBAC+CSRF+rate limit, capabilities, requested/reported/
  verified configuration, ACK/evidence/history/errors. DOM вывод через textContent.

Схема:0007_live_control добавляет 7 таблиц,0008_control_evidence — ещё 1; всего 42
таблицы с учётом старой схемы/Alembic. Старые migrations/tables/replay не изменены.
Receipt содержит event/device/epoch/sequence/profile/packet SHA256, не показания
и не ключи; переживает разрешённый retention telemetry outbox. Исторические draft
rows без digest не backfill выдуманными фактами. На fresh acceptance baseline
и новые transitions создают настоящие receipts.

## Nonce и recovery

AES96-bit nonce = epoch 32BE || sequence64BE. PG заранее фиксирует boot range 10000
выше всех выданных значений; fresh UUID request связывает grant с этим процессом.
Range cursor не восстанавливается из старого файла. Переключения используют один
монотонный telemetry sequence, keys разных AEAD независимы. Лимит 2^32−1/epoch.
QoS1 повторяет ciphertext, не шифрует новый plaintext старым nonce.

Текущий agent продолжает отправку при отказе controller в пределах range. Новый
boot/исчерпание без authority — fail closed. Старый local state сверяется с PG;
отсутствующий ledger не переинициализируется молча. Одновременный rollback PG и
всех device snapshots с прежними keys не решается software counters: запрещён,
требуется новая epoch/keys. Это не hardware anti-rollback.

При неизвестном исходе нет rollback. Admin reconciliation открывает ≤120 s окно
наблюдения ТОГО ЖЕ ранее авторизованного ACTIVATE; без новой authenticated target
telemetry effective не меняется. PREPARE-only expiry/повреждённый ledger требуют
локальной операторской проверки/восстановления или reviewed provisioning;
универсальное удалённое исправление state не заявляется.

## Реальные результаты

Два собственных project: lcm-stage8-control и lcm-stage8-acceptance. Раздельные
credentials/volumes,3 devices alpha/beta/gamma; gamma capability-restricted Ascon.
Исходные рабочие volumes не подключались. CPU/RAM quotas и log rotation включены.

| Проверка | Наблюдаемый результат |
|---|---|
| Ascon baseline всех 3 | Receiver AEAD admission/outbox/Mongo; verified profile |
| Ascon→AES→Ascon alpha | Новые ciphertext действительно приняты своим AEAD; receipt/event references; оба соседа остаются Ascon |
| Concurrent controllers | Два real control-worker instances, новые sequence, без conflicting transitions/duplicate ACK records |
| gamma/AES | HTTP preflight rejection, команда не создана; device unsupported branch отдельно проверен на durable SQLite |
| Device restart | Новый зарезервированный range и принятая telemetry с большим sequence, профиль сохранён |
| Stale local snapshot | Нет новой принятой telemetry/нет silent downgrade; правильная копия восстанавливает работу |
| Worker restart между PREPARE/ACTIVATE | Real READY retry/cached response, затем реальный target packet |
| ACTIVATE ACK loss | EFFECTIVE только по target telemetry, ACK timestampNULL; нет rollback |
| Broker outage | Нет ложного effective; после восстановления protected flow продолжается |
| PG outage до/после device activation | Durable intent/replay/evidence согласованы, после recovery принимается настоящая target telemetry |
| Grace expiry | UNKNOWN_OUTCOME; ручное bounded reopening и новая AEAD telemetry подтверждают результат |
| Missing device state | Agent exit1,0 новых accepted messages; правильная копия позволяет restart |
| Late ACK после effective | Точные bytes настоящего сохранённого agent ACK пересланы поTLS; reported/ACK time обновлены, effective_event/confirmed_at неизменны |

Девять recovery cases: stage8-acceptance-recovery.json. Последний late ACK case —
stage8-late-real-ack.txt/json. Никаких fake ACK или генерации simulator receipt.
Клиент переотправляет именно уже созданный real DeviceState ACK с прежним MAC.

20live negative checks: incorrect/non-ASCII MAC, wrong direction key, чужой topic,
unsupported profile, epoch/sequence/identity conflicts, expired retained command,
ACL publication/read denial, contradictory/duplicate ACK, HTTP anonymous/viewer
access. Проверяются PG records и продолжающаяся telemetry, не строкаPASS.
Unit tests дополнительно проверяют positive prior epoch, invalid JSON/NaN/types,
missing keys, no ACTIVATE without PREPARE, rollback и nonce reuse rejection.

## Тесты и выявленные дефекты

Полный pytest: **401 passed, exit0**, без skips, с настоящими PG/Mongo в отдельном
project. Это 337 прежних+64 новых cases. Изменены только закономерные прежние ожидания:
registry теперь содержит 2 профиля, schema 42 таблицы, Alembic head0008. Защита не
отключалась. Existing synthetic RF/IF fixtures в regression suite остаются
синтетическими; на реальном лабораторном dataset не было train/holdout inference.

Крипто:99 checks в отдельном KAT/boundary/tamper run. Сохранены 4 Ascon-c vectors;
точные 2 CAVP AES cases (пустойPT, AAD0/128) и supplementary zero-key examples;
canonical HMAC expected bytes независимо получены OpenSSL dgst. Источники:
[SP800-38D](https://csrc.nist.gov/pubs/sp/800/38/d/final),
[SP800-232](https://csrc.nist.gov/pubs/sp/800/232/final),
[CAVP](https://github.com/pyca/cryptography/blob/main/vectors/cryptography_vectors/ciphers/AES/GCM/gcmEncryptExtIV128.rsp).
Не заявляется FIPS/constant-time certification.

Девять injected mutants: отключённые AES tag rejection/control MAC/replay,
premature effective, missing device binding/capability, повторный nonce range,
commit до атомарного завершения, contradictory ACK. Все 9 killed по поведенческим
assertions, не SyntaxError/import failure; unmutated baseline проходит.
Временные copies, рабочая ветка не мутировалась. Таблица defect→test→exit содержится
в stage8-final-mutations.json. Это coverage, не девять реальных exploits проекта.

Реальные defects/исправления этого этапа:

- Слишком длинный delivery status откатывал подтверждение PG; исправлен и проверен.
- Unicode MAC вызывал TypeError за пределами ValueError handling; strict hex64
  теперь отвергается предсказуемо, live device после malformed MAC работает.
- Retention мог оставить effective без первичной записи outbox: добавлен durable
  receipt, реальный SQL retention/receipt-failure rollback tests проходят.
- Поздний подлинный ACK сохранялся, но не обновлял reported/ACK metadata. Новый PG
  test сначала **упал** на 68c0767, после 282a49f проходит; реальный TLS replay
  сохранённого agent ACK подтверждает исправление без смены effective evidence.
- Harness: root без DAC capabilities не мог открыть private state; исправлен
  пользователь исполнения. Rate limit не отключали — harness соблюдает 2 s.
- Fresh startup не включил Mongo в explicit service list; обнаружен DNS failure.
 1286 accepted events остались pending, после запуска Mongo снимок 1695/1695 найден.
  Это восстановление зафиксированного outbox, не доказательство всех device losses.

Старые PostgreSQL/Mongo/Outbox/replay/Flask/Socket.IO проверки сохранены. Real
transport и HTTP/Socket.IO smoke отдельно прошли; command roles не смешивались.
Mongo validator upgrade выполнен 2 раза,12326 documents и всеindexes сохранены.
Временное возвращение old enum тестируется только на собственной БД с остановленным
relay; validator восстановлен, data/volumes не удалялись.

## Производительность

Полная методика/таблицы: [CRYPTO_SWITCH_BENCHMARK.md](CRYPTO_SWITCH_BENCHMARK.md).
Software/x86_64, Python 3.12.16, cryptography 50.0.2/OpenSSL 4.0.3. Micro256 bytes:
Ascon encrypt/decrypt p50≈387.9/391.4 µs; AES≈1.27/1.28 µs,3 повтора.
Native AES против pure Python reference — сравнение реализаций, не стойкости.
Четыре measured transitions intent→effective228.476–525.819 ms (mean328.549 ms).
ACTIVATE→ACK≈82–83 ms, ACTIVATE→verified telemetry100.243–413.468 ms.
В 6static windows92/92 committed observations найдены вMongo. CPU/RSS/throughput,
p95/p99 и limitations сохранены raw, не заменены красивой итоговой цифрой.

Benchmark source 68c0767; последующее 282a49f меняет только late ACK metadata,
не primitive/performance code. Старые benchmark reports не переписаны.
Изолированный transient switching CPU и реальная общая потеря device messages
не определены; Docker snapshots/PG-Mongo parity не выдаются за эти показатели.

## Границы результата

- Проверены Python software agents. Нет ARM/Raspberry Pi/physical sensor tests,
  secure element, энергии/массового load/HA или remote key distribution.
- PG и владелец локального provisioning — trusted authority; application audit
  append-only, но это не externally signed/WORM proof против владельца всей БД.
- HMAC скрывает ключи, но не metadata от broker. TLS сохраняется обязательно.
- Paho outgoing queue не durable device outbox: unaccepted messages могут потеряться
  при crash. PG-committed outbox доставляется идемпотентно; exactly-once не обещается.
- Audit/nonce/replay records не очищаются автоматически. Lease cap10000/device
  требует reviewed maintenance без reset counters. Disk quotas отдельного FS нет.
- RF/IF остаются RESEARCH/DEMO, trusted_detector=false. Старые PCAP/datasets/models/
  frozen plans и результаты сохранены. Control packets в них не добавлялись.
- Ascon/AES не образуют hierarchy по «силе». «Магма»/CRISP/FastAPI не реализованы.

Будущая автоматизация требует отдельно утверждённого actuator authorization,
проверенных сигналов/детекторов, критериев выбора профиля, capability проверки
реальных устройств и аппаратных измерений. Этапы 7.5c/9 автоматически не начаты.
Push/merge/main changes не выполнялись.

## Сохранность и журнал проверок

Проверены 764 прежних private file hashes и 141 Git report исходного f6f3c23: изменений 0.
Ground-truth v2.2 повторно сверил 2269 исходных packets, class counts 1509/190/570
и files_modified=false. Ни модели, ни frozen plan не изменились; original plan
SHA256 a4f8284151fb2beb53e7d45b2b30e017975eac68ad240eb239717901d001868f.
Critical 16 runtime sources побайтно совпали в runtime/tests images.

Команды/UTC/exit codes: docs/reports/stage8-*.txt. Machine results: registry,
crypto-kat, final-roundtrip, live-negative, acceptance-recovery, late-real-ack,
final-mutations, mongo-validator, crypto-microbenchmark, switch-benchmark,
runtime-resources, runtime-source-check и preservation.json. Исторические
неуспешные attempts не удалены; final successful run указан отдельно.

## Git и завершение

Логические code commits: d699ff1 (AES dispatch), d05010c (live control/agent),
1008a35 (recovery/receipt persistence), 68c0767 (security+benchmark),
282a49f (late authenticated ACK). Финальный docs commit указан в отчёте Codex.
Полный список файлов: reports/stage8-files.txt. Команды и exit codes:
reports/stage8-test-summary.json и соответствующие .txt logs.

Оба собственных stage8 project остановлены без -v. Ни одного работающего их
контейнера не осталось; по 19 volumes каждого сохранены, включая keys/PG/Mongo/
device counters. Исходные project/volumes прежних этапов не удалялись.
Known-secret scan текущих/исторических Git blobs, working tree и 2 images прошёл;
права private inputs 0700/0600 проверены. Это targeted known-secret audit, не
гарантия обнаружения любого неизвестного секрета. Ruff и git diff --check проходят.

Индекс reports с SHA256/runtime versions: reports/stage8-report-manifest.json.

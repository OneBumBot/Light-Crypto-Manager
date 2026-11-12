# Этап 12: результаты исследования и оптимизации

Работа выполнена в `feature/crypto-comparative-research` от чистого `feature/kuznyechik-mgm-integration`, SHA `20d298cc3b48f14920a00e9403bdaf0ff7e38c5a`. Проверенная версия рабочего контура — `bf8c7d5bfa84ed6120e0174c2b7500dc1da04af6`; последующие изменения касаются инструментов сравнения, инвентаризации и документации. SHA исходников каждого записавшего его эксперимента сохранён в JSON; контрольные суммы исходников и артефактов — в [evidence-index.json](reports/stage12/evidence-index.json). Финальный SHA отчётного коммита определяется `git rev-parse HEAD`, чтобы документ не содержал собственную невозможную самоссылку. `main` остался на `c352d817386a17fb244d3567b287af0412eed4e4`. Push/merge/rebase не выполнялись.

## Полученный результат

Три прежних AEAD сохранены. Для единственного профиля `kuznyechik-mgm-v1` добавлен явно выбираемый ограниченный локальный Go worker. Формат telemetry v2, wire name, ключи, ICN, HMAC, nonce authority, usage accounting и критерий effective не зависят от backend. По умолчанию остаётся one-shot; специальный Stage12 lab явно включает persistent. Сетевого криптосервиса нет, ключи передаются только через приватные pipes. Неизвестный backend, ошибка процесса или протокола приводят к `ProviderUnavailable`, без Ascon fallback. Неверный tag не возвращает plaintext.

Magma получила отрицательный gate **NOT_SUITABLE_FOR_CONTINUOUS_TELEMETRY** для текущего протокола. Она не добавлена в live registry, capabilities, provisioning, MongoDB enum или UI. Это результат исследования, а не неработающая имитация четвёртого алгоритма. Все реестры и страницы по-прежнему используют проверенные Ascon/AES/Kuznyechik.

## Что изменено

Изменены Python/native Kuznyechik adapter и metadata registry; добавлены Stage12 provisioning/install/run, инструменты native/Python сравнения, Magma расчёта, сетевых проверок, IPC recovery, mutations, графиков и preservation. UI уточняет, что implementation ID относится к **backend web-процесса**, а не является аутентифицированным фактом о внутренней реализации датчика. Криптографический профиль подтверждается реальной AEAD telemetry.

Полный список файлов — [CHANGED_FILES.txt](reports/stage12/CHANGED_FILES.txt); архитектурные изменения — [provider audit](STAGE12_KUZ_PROVIDER_AUDIT.md), [optimization](STAGE12_PROVIDER_OPTIMIZATION.md), [integration](STAGE12_SYSTEM_INTEGRATION.md). Исторические миграции и исходники шифров не изменялись; новых SQL migrations не потребовалось, head остаётся `0010_mgm_key_usage`.

## Provider и Python

Runtime использует прежний BSD-2-Clause `tarantool/go-gostcrypto`, pin `3791d459e0c35d051a691a3bd3a4a69f671258f5`. Новые версии проверены по upstream, а не предположены неизменными. Исходный Go executable воспроизводимо собран дважды: SHA256 `5e715633b674a09235ab1bfcbe99f0f283835fb20a7789b869f3e590eb68527a`. Новый dual-mode executable также совпал в двух сборках: `215ede6bfca73ef851bc37a565b864d40901b357c673f153ea0105ad932dedc3`. CGO выключен, зависимости локальные, сборка без сети.

Исследованы gostcrypto/MIT (Кузнечик есть, MGM API в проверенной версии нет), старый mosquito/PyGOST (MGM нет), ZvonokComGroup/PyGOST 5.12/GPL-3.0 (полный Python MGM), gost-engine/Apache-2.0 (native MGM есть, новый Python binding не проверен). Точные ревизии и хеши сохранены в [candidates.json](reports/stage12/candidates.json). У официальной 5.13 не удалось проверить архив из-за TLS certificate verification failure; проверку TLS не отключали. Поведение 5.13 не экстраполировано из 5.12.

**Выполнять Kuznyechik-MGM целиком на Python возможно.** Исследовательская строгая обёртка PyGOST прошла RFC 7801 block encrypt/decrypt и все 10 round keys, оба RFC 9058 A.1 примера, 31 точный cross-check, 93 повреждённых tag и 40 параметрических negatives. В raw API 5.12 воспроизведены неверная единица ограничения длины и приём одновременно пустых P/A при соответствующем внутреннем tag; wrapper закрывает эти случаи. Это не подтверждённые сетевые уязвимости LCM. Variable-time реализация, лицензия и отсутствие нового аудита не позволяют автоматически заменить ею runtime. Подробности — [Python evaluation](STAGE12_PYTHON_KUZNYECHIK_EVALUATION.md).

Worker сериализует запросы, связывает ответы с монотонным ID, ограничивает длины, deadline, число операций и lifetime. Cipher/MGM создаются заново; кэширования ключей нет. Parent recycle — 25 секунд/256 запросов, native lifetime — 30 секунд, exchange deadline — 5 секунд. Soft Go memory target 32 MiB работает внутри существующих жёстких service cgroup limits. GC zeroization не гарантируется; увеличение времени нахождения ключа в памяти явно признано риском.

Обнаружены и исправлены два adapter-дефекта: сохранение старого процесса при изменении пути executable и гонка EOF stderr с последним корректным stdout response. Последняя воспроизведена падающим тестом до исправления ([stderr-eof-before.txt](reports/stage12/stderr-eof-before.txt)); EOF теперь снимает регистрацию stderr, реальные bytes stderr по-прежнему означают отказ. Повреждённый/truncated stdout не принимается. Отдельно исправлены учёт warm-up CPU в benchmark и неполный охват новых незакоммиченных отчётов secret scan; итоговая offline-инвентаризация сканирует их явно.

## Производительность: алгоритм отдельно от реализации

Хост: AMD Ryzen 7 9800X3D, Linux x86_64, Python 3.12.16, Go 1.27.3-X:nodwarf5. Docker runtime использовал cryptography 50.0.2/OpenSSL 4.0.3; сведения о host OpenSSL CLI сохранены отдельно, это другой контекст. Среда и image IDs — [final.json](reports/stage12/final.json), [preservation.json](reports/stage12/preservation.json).

Матрица: 5 независимых процессов/ключей на каждую комбинацию 5 implementations × 4 payload (64/83/256/1024 B) × 2 AAD (128 B fixed/canonical telemetry), по 1000 измеряемых encrypt/decrypt пар после 20 warm-up. Процессы привязаны к CPU0; сервисы при microbenchmark остановлены. Сохранены исходные серии, повторные серии после EOF fix, отдельный immutable Stage11 executable и отдельные CPU прогоны. Итоговая выборка содержит 200 runs, CPU-выборка — 25; derived JSON не считаются новыми независимыми экспериментами. Нет CI из коррелированных пакетов, экстраполяции на ARM или подмены пропусков нулями.

83 B plaintext / 128 B AAD, медиана пяти run medians:

| Реализация | Encrypt, мкс | Authenticated decrypt, мкс | CPU, мкс/пара |
|---|---:|---:|---:|
| AES / cryptography native | 1.333 | 1.352 | 2.92 |
| Ascon / Python reference | 271.415 | 272.182 | 542.35 |
| Kuznyechik / исходный Stage11 Go one-shot | 2569.677 | 2566.586 | 3042.15 |
| Kuznyechik / bounded Go worker | 177.316 | 176.389 | 366.72 |
| Kuznyechik / PyGOST strict research | 2395.133 | 2394.622 | 4785.57 |

В отдельном контроле с **одним новым dual-mode binary** one-shot = 1620.972 мкс, worker = 177.316 мкс: около **9.14×** по encryption integration latency. Immutable Stage11 batch измерен позднее; причина его расхождения с новым one-shot batch не установлена. Частоты CPU, scheduler и внешняя нагрузка не изолированы. Нельзя выдавать межсерийное отношение за строго контролируемое ускорение или доказательство свойств алгоритма.

Python parent peak RSS в отдельных CPU runs — около 25.8–27.3 MiB, Go child peak — около 25.4–25.8 MiB; раздельные пики не складываются в выдуманный совместный максимум. Ciphertext expansion всех измеренных runtime AEAD — 16 B. Native probe отдельно измерил warm key setup 17.733 мкс, Seal/Open 137.722/136.900 мкс, startup+empty rejection 481.088/463.039 мкс, noncrypto echo IPC 2.825 мкс. Из этих разных интервалов ничего не вычиталось как «точное время шифра».

Исходные данные: [comparison](reports/stage12/comparative-final.json), [CPU](reports/stage12/cpu-final.json), [CSV](reports/stage12/run-summary.csv), [native](reports/stage12/native-instrumentation.json). Экспериментальные ограничения — [comparison methodology](STAGE12_CRYPTO_COMPARISON.md).

## Side-channel результат

Подтверждена key-dependent ветка в GF multiplication MGM, включая `JE` в сохранённом x86 objdump. `NewCipherCT` не доказывает постоянное время всего MGM. Timing screening: 5 процессов, 5000 samples/class/run; Welch t = −1.418, −1.996, 0.752, −0.815, −1.276. Уникальный nonce меняет промежуточные значения даже в fixed-key class; мощность такого screening ограничена. Это не доказательство отсутствия утечки и не демонстрация удалённого извлечения ключа.

Оптимизация не меняет GF arithmetic ради красивой скорости. Утечка не объявлена исправленной; lab-only сохраняется. Tag проверяется constant-time primitive provider до decrypt; при провале plaintext не выдаётся. GC, compiler, counter carry и Python table/bigint ограничения перечислены в [review](STAGE12_SIDE_CHANNEL_REVIEW.md). Whole-provider constant-time и сертификация не заявлены.

## Magma: проверка и отрицательное решение

Проверены upstream Go Magma/MGM tests и независимые Python RFC 8891 block, RFC 9058 A.2 Example 1/2: ciphertext/full 64-bit tag совпали, неверный tag отвергнут без plaintext. Это офлайн-проверки публичных векторов, не live release. Не путать Magma с произвольным ГОСТ 28147-89 S-box.

Расчёт использует RFC 9058 §6, размер блока/tag 64 бита, отдельные confidentiality/integrity bounds и conservative union bound по verification attempts и keys/epochs. Для AAD124/P83 — 27 блоков, для разрешённых максимумов AAD1024/P4096 — 640. Перебраны цели 2^-32/40/48, 1/3/30/300 keys/epochs, 16/1000 verification attempts. При цели 2^-32 и 1000 attempts для real-size примера допустимый q — **37/21/6** сообщений на ключ для 1/3/30 keys; при максимальных размерах положительного q в этих настройках нет. Это расчёт при явно выбранных допущениях, не универсальный лимит стандарта «58».

Проектный ICN: 0|counter63 BE под новым независимым per-device/profile/epoch key; global sequence не усекать и не считать расходом ключа. Текущий lease 10000 несовместим с таким budget; нужны versioned short grants, atomic per-key invocation/block/verification accounting, burn без refund после crash, защищённая установка нового ключа и явная миграция epoch binding. Этот rekey lifecycle **не реализован**; стоимость rotation — `not_measured`. При exhaustion должен быть stop, а не reset/fallback. См. [budget](MAGMA_MGM_SECURITY_BUDGET.md), [rotation design](MAGMA_KEY_ROTATION_DESIGN.md).

## Настоящий MQTT/TLS, HTTP и браузер

Новый проект `lcm-stage12-crypto-research-lab`: 3 независимых software identities, новые CA/TLS/MQTT/HMAC/AEAD keys, PG/Mongo/SQLite volumes. Alpha/beta поддерживают три профиля, gamma — только Ascon. Старые контуры не использовались.

Пять окон по 20 секунд при 1 Hz: alpha Ascon, Kuz worker, AES, Ascon повтор, Kuz one-shot; beta/gamma постоянно Ascon. Это объявленная смешанная нагрузка, а не стенд из трёх AES-устройств. В каждом окне **60 scheduled / formed / publish calls / queued / PUBACK / PG / Mongo**; для всех 300 сообщений сверены конкретные device/epoch/sequence identities. PUBACK отдельно не засчитан durable admission.

Медиана alpha sensor→receiver-created: 3.124 / 5.297 / 2.466 / 3.058 / 8.095 ms. Sensor→Outbox delivered_at после Mongo ACK: 192.680 / 157.858 / 305.191 / 329.561 / 365.335 ms. Общий host wall clock; accuracy отдельно не измерена. Это не изолированные network/PG commit интервалы; relay phase существенно влияет на delivery. Снимки суммарного Docker CPU: 28.67/24.18/10.19/18.69/34.37%; RAM 606/626/628/623/652 MiB. Пять снимков не являются доказательством причинной разницы CPU между алгоритмами.

Цепь Ascon→Kuznyechik→AES→Ascon выполнена через настоящий admin HTTP+CSRF, MQTT/TLS/HMAC, PREPARE/READY/ACTIVATE, Device Agent, receipt и Mongo. В основном сетевом сценарии request→observed effective: 1.03–2.06 s; это polling-bound наблюдение, ACK хранится отдельно. Chromium прошёл отдельные dashboard и /control journeys, по 4 реальных перехода каждый, reload, viewer read-only, gamma unsupported, независимость соседей, mobile и XSS/attribute/audit/ML injection negatives. Fixture injection проверки отделены от настоящих сетевых данных.

Итог после остановки publishers и drain:

| Показатель | Факт |
|---|---:|
| PostgreSQL committed / Mongo delivered | 7689 / 7689 |
| Ascon / AES / Kuznyechik records | 7351 / 41 / 297 |
| Подтверждённые transitions | 27 из 27 |
| Authenticated ACK | 52; два ACTIVATE ACK намеренно потеряны |
| Effective receipts | 30, включая 3 начальных baseline |
| Pending / dead Outbox | 0 / 0 |
| Rejected / replay observations | 19 / 1 |
| Duplicate formed nonce / sequence | 0 / 0 |

Глобальная исходная совокупность всех planned messages за recovery-эксперименты — `not_measured`; равенство PG/Mongo после drain не объявляется универсальным lossless delivery. Сохранено 24 usage reservations; alpha/beta резервировали 180000/60000 MGM invocations, включая сгоревшие неиспользованные grants. Verification attempts alpha — 302. Restart worker не сбрасывает этот authority. Все финальные effective profiles — Ascon, соседи не переключались.

## Negative, recovery, mutation и regression

Реальный poison: 19 malformed сообщений, включая wrong tag/AAD/types, 19 rejected, 3 valid accepted, один replay без duplicate admission. Отслежены 11 секунд обычного наблюдения и 5 секунд после явного receiver restart; processing failures и вызванных malformed reconnect/subscription циклов не обнаружено. Это bounded observation, не обещание бесконечной доступности. Security rejected identity остаётся неатрибутированной; malformed не меняет admission state.

Проверены реальные Mongo/control/policy/PG/broker/device/receiver outages на MGM, восстановление доставки, manual ACK при failed commit, persistent MQTT session и idempotence. В семи fault cases наблюдение новых durable admissions после восстановления заняло около 2.15–2.32 s; полное время включает shutdown/startup/held interval и сохранено отдельно. Дополнительно убиты реальные Go children receiver/agent; последующая корректная telemetry принимается, usage authority не сброшен. Проверены lost ACTIVATE ACK, grace expiry→UNKNOWN_OUTCOME→явная bounded reconciliation; effective возникает лишь по новой AEAD telemetry. Missing SQLite завершает agent exit1 без создания state, stale restore не даёт admission/downgrade, возврат captured current state требует нового grant.

**Baseline: 868 passed, 0 skipped, exit0. Итог: 882 passed, 0 skipped, exit0 (42.00 s).** Старые Ascon/AES KAT, malformed/replay/nonce, SQL/Mongo/Outbox, control, Policy/ML trust, RBAC/CSRF/Socket.IO, Ground Truth tests сохранены. Worker negatives — 14 passed; KAT/dispatch/IPC серия — 66 passed. Race tests Go и upstream Magma/MGM tests прошли. Browser/network/outage эксперименты выполнялись отдельно от pytest, не прибавлены к его счётчику.

Mutation: **25/25** дефектов обнаружены поведенчески; baseline mutation selection — 176 passed. Mutated test exit1, runner exit0; SyntaxError/ImportError не засчитывались. Сохранены прежние мутации, добавлены смешивание response ID, plaintext-on-error, missing backend fallback, повторное списание grant budget и EOF race. Magma live mutations неприменимы, поскольку runtime-профиля нет; это не скрытый PASS. Детали injected defect/test/expected/actual/exit — [mutations-release.json](reports/stage12/mutations-release.json).

## Сохранность и границы вывода

Проверены неизменность 737 исторических tracked artifacts и 764 архивных файлов, отсутствие reuse новых 14 приватных keys с 402 историческими key values, права private files/dirs, role scoping, secrets в образе/logs/API/Git, изоляция network/volumes и CPU/RAM/log caps. Финальная инвентаризация дополнительно сканирует все новые отчёты и документацию. Старые SQL volumes не запускались и не удалялись; `down -v` не использовался. Старый build helper мог использовать существующий Go compilation cache; это не nonce/SQL authority. PCAP/datasets/models/plans/исторические отчёты не переписывались.

Policy остаётся **DRY_RUN**, реальные команды — **MANUAL_AUTHORIZED_CONTROL**, RF/IF — **RESEARCH/DEMO**, `trusted_detector=false`. Автоматического ML-control и обучения нет. Runtime proto/keys/replay/usage не ослаблены. Все Stage12 сервисы остановлены, volumes и ключи сохранены для resume.

Ограничения: software x86 lab, один host, без ARM/Raspberry Pi измерений, независимого side-channel аудита и сертификации. TLS download failure ограничила исследование Python 5.13. Межсерийные scheduler/frequency effects, малый сетевой cohort, короткие окна, отсутствие точной clock accuracy и некоторых ранних top-level SHA/argv в raw logs явно сохранены в provenance inventory. Количество тестов не доказывает криптостойкость или качество IDS.

Следующий отдельный этап: независимый аудит MGM arithmetic/compiler, platform-specific ARM KAT/timing/recovery и hardware runs; при необходимости — версионированный rekey/short-lease design с aggregate budget, а не автоматическое включение Magma. Stage13 здесь не начат.

## Воспроизведение и графики

Запуск/stop/resume — [STAGE12_SYSTEM_INTEGRATION.md](STAGE12_SYSTEM_INTEGRATION.md), команды/exit codes — [COMMANDS.md](reports/stage12/COMMANDS.md). Не переиспользовать чужой directory/project, не удалять SQLite/volumes. Приватные аккаунты остаются в `accounts/*.password`, значения в отчёты не выводятся.

10 семейств PNG/SVG: [encrypt](reports/stage12/figures/encryption_payload.svg), [decrypt](reports/stage12/figures/decryption_payload.svg), [throughput](reports/stage12/figures/throughput.svg), [CPU](reports/stage12/figures/cpu.svg), [RSS](reports/stage12/figures/rss.svg), [expansion](reports/stage12/figures/ciphertext_expansion.svg), [startup/IPC](reports/stage12/figures/startup_ipc_native.svg), [MQTT](reports/stage12/figures/mqtt_latency.svg), [switch](reports/stage12/figures/switch_latency.svg), [usage/rotation](reports/stage12/figures/usage_rotation.svg). Magma отсутствует на live графиках; неизмеренная rotation не изображена нулём.

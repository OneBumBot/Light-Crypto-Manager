# Stage11: Kuznyechik-MGM integration

Статус: **проверенная software-lab интеграция, не production/ARM/сертифицированное применение**. Система реально шифрует telemetry третьим AEAD, receiver аутентифицирует MGM, PG/Outbox/Mongo сохраняют записи, verified effective меняется только по принятой telemetry. Magma/Stage12/7.5c не реализовывались.

## Исходное состояние и изменения

Baseline: `feature/system-performance-validation`, `d226fbc56068caa5a2685d31a89eb0c85f8efe4c`, clean tree, Alembic0009. Новая ветка `feature/kuznyechik-mgm-integration`. Main не изменён, push/merge/rebase не выполнялись. Logical commits отделяют provider verification, integration/accounting, role security, migration/browser checks и отчёты. Точный validation source SHA и hashes: `docs/reports/stage11/source-manifest.json`; последний documentation commit не меняет проверенные исходники.

Provider: tarantool/go-gostcrypto `3791d459e0c35d051a691a3bd3a4a69f671258f5`, BSD2, Go CT Kuznyechik + MGM. Runtime не связывается с GPL fork, применённым только для независимого сравнения. Параметры: block128/key256/ICN127 significant bits/full tag128/AAD. Сборка pinned/offline, source hashes и license notices сохранены. [Полный выбор](STAGE11_PROVIDER_SELECTION.md).

Новый explicit dispatch без Ascon fallback;32B per-device key; deterministic ICN; conservative per-key usage и verification budgets; additive migration0010; private provisioning alpha/beta с тремя профилями, gamma Ascon-only; strict Mongo collMod; UI eligibility по capability и release authorization. Web не получает MGM/control keys. PREPARE/ACTIVATE/HMAC/TTL/replay/Outbox/effective invariants сохранены. Policy DRY_RUN, RF/IF RESEARCH/DEMO и trusted_detector=false.

## Воспроизводимый запуск

Требования: Linux x86_64 software host, Docker+Compose v2, Python3.12-compatible environment, OpenSSL CLI, доступ к pinned container images/Python packages при первой сборке. Для host provisioner нужны existing requirements; при чистом checkout:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements/publisher.txt -r requirements/receiver.txt -r src/web/requirements.txt
.venv/bin/python -m scripts.kuz_lab prepare --directory .local-runtime/stage11/new-lab --project lcm-stage11-kuznyechik-new
.venv/bin/python -m scripts.kuz_lab start --directory .local-runtime/stage11/new-lab --build
```

Prepare **только новый** directory/project. Создаются новые CA/TLS/MQTT/HMAC/Ascon/AES/Kuznyechik keys, three durable SQLite identities и independent volumes. Migrations, strict Mongo additive upgrade, explicit test-lab authorization, manual control и Policy DRY_RUN поднимаются скриптом. Readiness требует настоящих первых PG/Mongo telemetry events. Выводится loopback URL с назначенным портом; постоянного пароля в документации нет.

Аккаунт admin: `demo-admin`; приватный пароль в `.local-runtime/stage11/new-lab/accounts/admin.password` (0600). Viewer/operator аналогично `demo-viewer`/`demo-operator`. Открыть `/control`, выбрать alpha, подтвердить baseline по telemetry, выбрать Kuznyechik-MGM, отдельно подтвердить запрос. Дождаться receipt и confirmed effective. Затем AES→Kuznyechik→Ascon; beta/gamma сохраняют своё состояние. Не считать HTTP202 или ACK подтверждением effective.

```bash
.venv/bin/python -m scripts.check_kuznyechik_mqtt --directory .local-runtime/stage11/new-lab --output /tmp/stage11-switching.json
.venv/bin/python -m scripts.kuz_lab stop --directory .local-runtime/stage11/new-lab
# Продолжение того же стенда: старые keys/state сохраняются
.venv/bin/python -m scripts.kuz_lab start --directory .local-runtime/stage11/new-lab
```

`stop` сохраняет volumes; `down -v` не используется. Не удалять installed markers/SQLite/PG state для повторной демонстрации. Утрата nonce authority, несогласованный restore или исчерпание budget требуют reviewed rekey/new epoch, не reset. Для нового независимого эксперимента выбрать **другое** имя проекта и directory.

Browser tests требуют Playwright1.56.0 и совместимый Chromium. В проверенной среде использован existing cached `uv` environment и `.local-runtime/browsers`; на чистом хосте сначала установить browser через Playwright штатным способом. Это отдельная test dependency, не frontend runtime.

## Команды и наблюдаемые границы

- Baseline full Docker pytest:739 passed, exit0.
- Final full Docker pytest: **868 passed,0 skipped,38.09s, exit0**, `full-regression-release.txt` (предыдущий post-isolation прогон867 passed); без сокращения прежних assertions и пропусков.
- Provider suite: RFC7801 block/key-schedule и оба RFC9058 A.1 examples; exact bytes, corrupted key/nonce/AAD/ciphertext/tag, lengths/types, empty/partial/bounds.
- Independent comparison54 cases,108 invalid-tag rejections, exit0; local reproducible builds имеют одинаковый SHA256 при одной toolchain.
- Main network script подтверждает все4 направления реальным HTTP→MQTT/TLS/HMAC→Device→AEAD/PG→Mongo путём. Каждый receipt связан с event/sequence/profile. Отдельно Chromium card и `/control` journeys.
- Poison MGM:19 rejected,0 malformed admissions,3 valid admissions,1 duplicate replay/0 duplicate admission. За10 samples≈11s не было receiver processing errors/connections/subscription changes; после explicit receiver restart5s counters стабильны. Это bounded observation, не обещание отсутствия любых reconnect при любых условиях.
- Seven real outages/restarts: Mongo, Control Worker, Policy Worker, PostgreSQL, broker, alpha, receiver. Verified MGM profile сохранён, соседние устройства продолжали передавать там, где основной транспорт/PG оставались доступны. Pre-restore committed cohort доставлен после восстановления. Observation после Compose readiness≈2.1s включает probe overhead, это не точная физическая downtime.
- Lost ACTIVATE ACK: только READY ACK, effect подтверждён настоящей MGM telemetry. Delay20s/TTL15s: UNKNOWN_OUTCOME не меняет verified state; manual reconciliation открывает только наблюдение, затем новый accepted packet подтверждает result.
-20 mutation checks killed поведением. Первоначально Ascon dispatch defect пережил direct primitive KAT; новый внешний dispatch-KAT закрыл реальный пробел покрытия. Невалидные import/syntax/build результаты не засчитываются.

Подробная матрица: [STAGE11_INTEGRATION_TESTS](STAGE11_INTEGRATION_TESTS.md). Сравнение реализаций и ограничения статистики: [STAGE11_CRYPTO_BENCHMARK](STAGE11_CRYPTO_BENCHMARK.md). Формальное ICN/budget/recovery обоснование: [KUZNYECHIK_NONCE_AND_KEY_BUDGET](KUZNYECHIK_NONCE_AND_KEY_BUDGET.md).

## Найденные ошибки и ограничения

Подтверждённый внутренний extension defect: прежний двухпрофильный else-dispatch направил бы третий descriptor в Ascon. Он исправлен **до** регистрации третьего provider; не объявляется эксплуатацией прежнего двухпрофильного сетевого пути. Выявлены anonymous auxiliary volumes базовых образов для broker logs/Mongo config; заменены explicit Stage11 project-scoped именами, прежние volumes сохранены. Найден лишний доступ web role к новому MGM key через legacy registry; key projection исправлена, отдельный image/volume audit проверяет отсутствие MGM/control keys у web.

Две первоначальные browser-test ошибки ожидания (hidden option и проверка gamma до получения её snapshot) исправлены как ошибки теста; не засчитываются как product/mutation vulnerabilities. Ошибка переноса RFCplaintext hex обнаружена exact KAT и исправлена по RFC. Исходные неуспешные журналы сохранены отдельно.

MGM multiplication содержит secret-dependent branches; upstream CT cipher experimental. Whole-provider timing resistance, GC zeroization, ARM и независимый security audit не доказаны. Поэтому допускается только явно авторизованный isolated software lab. Система не сертифицирована как СКЗИ; ГОСТ-алгоритм не означает regulatory compliance. Совместный откат PG+SQLite без внешнего monotonic anchor требует новых ключей/эпохи.

Этап12 логично посвятить независимому audit/provider hardening и физическому ARM стенду с измерениями; Magma требует отдельного обоснования64-bit bounds, nonce/usage/rotation и provider/KAT/E2E gates. Это рекомендации, работы этапа12 не запускались.

## Итоговые измеримые результаты стенда

Project `lcm-stage11-kuznyechik-live`, final regression source `359320ed83dcba506b3c487aaff6f7a3c6005c73`; последний network snapshot source `1148137cd953a4f9f6f0f4c6a8f1e9afdcb1f613` (runtime/source hashes и image IDs в JSON; последующий коммит документации не меняет исполняемый код).

| Показатель | Фактическое значение |
|---|---:|
| Provisioned software devices |3|
| PG committed / Mongo stored после quiescence|11312 /11312|
| Ascon /AES /Kuznyechik accepted|10390 /70 /852|
| Реальные transitions /confirmed|35 /35|
| Финальные failed/unknown|0 (один UNKNOWN_OUTCOME наблюдался и reconciled отдельно)|
| Authenticated ACK /effective receipts|68 /38 (включая3 baseline receipts)|
| Outbox pending/dead|0 /0|
| Invalid telemetry rejected /replay observations|19 /2|
| Delivery error /retry observations|5 /5, в controlled outages; после drain недоставленных committed событий нет|
| Agent formed records|11309; manual poison probe admissions считаются отдельно|
| Повторы sequence /nonce в agent journals|0 /0|
| MGM reserved invocations alpha /beta|150000 /70000; не равны числу реально выполненных MGM encryptions|
| MGM verification attempts alpha /beta|856 /0|
| Исторические tracked /private archive files неизменны|642 /764|
| Независимые приватные key values проверены|14|
| Mutation checks|20/20 behavioral failures, runner exit0|
| Полная регрессия после isolation fix|868 passed,0 skipped,38.09s, exit0|

Бюджет beta расходуется консервативно на boot ranges, хотя beta всё время шифровала Ascon. Gamma не имеет Kuznyechik key/capability; её имеющийся legacy AES key сам по себе не даёт права переключения. Planned publications и global sender loss: **not_measured**; агрегатное равенство PG/Mongo не объявляется доказательством lossless всех запланированных отправок.

Финальный validated four-direction run: request→наблюдённый effective0.580/0.277/0.804/0.551s для Kuznyechik/AES/Kuznyechik/Ascon. Полная последующая проверка Mongo измеряется отдельно; SQL created_at/confirmed_at сохранены. Ранние отчёты `real-switching*.json` до исправления границы timer включали последующую проверку history; для чистого observed-effective использовать `real-switching-validated.json`.

Static MQTT windows: каждый8s/16 admissions,16 Mongo docs. Median measured_at→receiver-created_at: Ascon3.642ms, AES2.501ms, Kuznyechik9.589ms. Это timestamp interval до commit boundary, не чистый network RTT или PG commit duration. CPU snapshots всего работающего стенда37.23/43.69/50.33% (100%=один core), RAM651.8/653.69/664.02MiB. По одной короткой серии на профиль, без устойчивых tail/scale выводов.

Все тестовые сервисы остановлены; volumes, keys, SQLite и command/replay/usage authorities сохранены. Исходные anonymous auxiliary volumes тоже не удалялись. New private material отсутствует в проверенных Git/report/image files/logs; web volume не содержит MGM/control keys. Это не общий аудит всех возможных исторических секретов или доказательство отсутствия side channels.

Дополнительно `scripts.check_kuz_sqlite_recovery` проверил настоящий agent на MGM при устаревшем Ascon SQLite snapshot и при отсутствующей БД. Stale state не получил admission/downgrade; missing state завершил agent с ожидаемым exit1 без autoinitialization. Затем восстановлен только captured current MGM state, получен новый boot grant и принята новая MGM telemetry. Harness exit0. Это одноразовый fault test отдельного lab: private backups не перезаписываются при повторном запуске. Полная безвозвратная потеря authority всё равно требует reviewed rekey, а не пересоздания старой БД.

Полный список изменённых файлов (код, migration, тесты, Compose adapter, документация, исходники provider и отчёты): `docs/reports/stage11/changed-files.json`. Метаданные source/commands/exit codes и hashes артефактов: `docs/reports/stage11/report-index.json`.

# Stage16 — итоговый release candidate

**COURSEWORK_RELEASE_CANDIDATE_READY** для основного изолированного software demo. Статус относится к исследовательскому прототипу, не production/IDS/криптографической сертификации. Shadow в основном demo: **OPTIONAL_RESEARCH_DEMO_UNAVAILABLE**; это не скрытый working component. Его capture namespace, current-source parity и trusted model mounts здесь не provisioned, основной продукт от них не зависит.

## Версии и изменения

Исходная ветка `feature/online-shadow-ids-validation`, SHA `b2317f94b9198b6300d49d9e5effd11a7efee298`. Итоговая ветка `feature/final-integration-stabilization`. Последний проверенный code/test source: `d1dfbf4f8a143e585aacfbe2ca83ec57ccaf6635`. Финальный documentation/evidence SHA определяется `git rev-parse HEAD` и приведён в итоговом сообщении: документ не содержит невозможную ссылку на собственный будущий commit. Main не изменён, push/merge/rebase не выполнялись.

[Полный список изменений](reports/stage16/changed-files.txt), [индекс SHA-256](reports/stage16/artifact-index.json), [приёмочная E2E matrix](STAGE16_E2E_TEST_MATRIX.md). Изменения ограничены runner/probes/recovery/evidence, eight guard tests, одним scoped mobile-history fix, Compose Stage16 overlay и документацией. Crypto providers, packet v2, key/nonce construction, HMAC protocol, Policy FSM/worker и старые migrations не переписаны. Alembic head `0011_policy_throughput`, новых migrations нет.

## Что реально работает

Единый `scripts.stage16_demo`: preflight, prepare, start, status, smoke, stop, resume, evidence. Основной `lcm-stage16-final-demo-main` имеет три настоящих Device Agent процесса: Alpha/Beta с Ascon/AES, Gamma Ascon-only по provisioned capability. Новые независимые TLS CA/credentials, per-device/per-algorithm AEAD keys, per-direction HMAC keys, PG/Mongo и Device SQLite. Не физические IoT/ARM устройства.

Readiness проверяет новые committed PostgreSQL и Mongo identities от всех трёх устройств после start/resume. MQTT PUBACK, PG commit и Mongo projection не смешиваются. Receiver проверяет AEAD/tag/AAD/identity; PG транзакционно выполняет replay admission, security journal, Outbox и eligible effective receipt. Relay доставляет Mongo idempotently по device:epoch:sequence.

HTTP Admin+CSRF создаёт durable intent. Реальные MQTT/TLS HMAC PREPARE/READY/ACTIVATE/ACK выполняются агентом. Signed ACK из его SQLite проверяется read-only и сопоставляется с PG canonical body digest. Только новая target-profile AEAD telemetry даёт EFFECTIVE_CONFIRMED. Нет AckSimulator, прямой подмены receiver admission или fake Mongo inserts. Beta/Gamma не переключаются при Alpha request. Viewer/Operator403, missing CSRF400, unsupported Gamma409.

| Контур | Работающих agents при опыте | Quiescent PG/Mongo | Confirmed transitions | Authenticated ACK |
|---|---:|---:|---:|---:|
| Основной final demo | 3 | 5838 / 5838 | 14 | 28 |
| Final clean-checkout realm | 3 | 278 / 278 | 4 | 8 |
| Ранний clean-checkout trial, сохранён отдельно | 3 | 143 / 143 | 2 | 4 |

Во всех указанных stopped checkpoints: Outbox delivered, pending0, exact identity matching, duplicate identities0. Количество сформированных/published/PUBACK сообщений Stage16 отдельно не инструментировано — оно не объявлено равным admissions. Active clean snapshot137PG/135Mongo был pipeline-in-flight, не loss; stopped checkpoint143/143 раннего trial и последующие финальные records сверены отдельно. Переходы включают реальные операции ранних harness attempts, не являются независимыми статистическими повторами.

## Stop/resume и ограниченные отказы

Полный stop/resume сохранил прежние PG/Mongo identities, команды, receipts, private material, SQLite profile/ledger; новые nonce ranges выше прежних и не пересекаются. Initial setup не повторяется. Эти ranges — authenticated sequence reservations: AES/MGM получают из них deterministic nonce/ICN, Ascon сохраняет прежний CSPRNG128-bit nonce. Полной Ascon IV trace Stage16 нет, поэтому exhaustive collision absence не заявляется. Missing marker/volume reference fixtures отказали до старта, реальные volumes/SQLite не удалялись. После auxiliary guard ещё раз проверены два resume и настоящий smoke на том же основном state.

Реально проверены receiver restart, Mongo outage с pending/drain, PG outage с честным HTTP503, Device Agent restart/nonce continuity, Policy unavailable и Control Worker interruption. Pending request при остановленном controller не стал ложным effective, после восстановления подтверждён новой telemetry. Режимы TLS/HMAC не отключались. Тайминги и границы наблюдения: [security/recovery](STAGE16_SECURITY_AND_RECOVERY.md), [raw report](reports/stage16/recovery.json). Это не гарантированный RTO или100% отказоустойчивость. Shadow failure не повторялся, поскольку он не активен.

## Чистый checkout и UI

Отдельный detached clean Git worktree, новая virtualenv с pinned requirements, fresh keys/volumes: preflight→prepare→build/start→status→real smoke→stop→resume→evidence→stop, все9 команд exit0. Холодный source `0bb46b7`; затем на source `d1dfbf4f8a143e585aacfbe2ca83ec57ccaf6635` проверены latest helper/resume/smoke/stop в том же clean checkout. Между ними product prepare/start/crypto/receiver code не менялся; smoke получил явное ожидание существующего2s admin cooldown. Private models и прежний state в checkout не копировались. Это проверка на том же физическом host, не независимый domain или обещание bit-for-bit сборки на любой платформе.

Настоящий Playwright/Chromium: Admin/Operator/Viewer, desktop1440×1000 и mobile390×844,15 итоговых screenshots, JS errors0. Пять mobile страниц укладываются в viewport. Проверены monitoring, device card, history, security events, Policy и manual control, два browser switches с новой telemetry; Shadow screenshot честно показывает unavailable/empty scores. Core demo проверен с blocked external CDN, legacy Bootstrap-dependent flows не объявлены полностью offline certified. Отдельная legacy DOM-XSS проверка прошла4payloads в каждом из трёх contexts. [Снимки и metadata](reports/stage16/browser-final.json).

## Найденные и исправленные проблемы

1. Docker auto address pools исчерпаны сохранёнными сетями. Использована проверяемая explicit disjoint subnet, без удаления старых сетей.
2. History имела document width570px при mobile390px. Добавлен внутренний scroll/table wrapper, пять страниц повторно проверены. Framework/design не переписаны.
3. Image-declared Mongo configdb/Mosquitto log anonymous volumes первоначально не учитывались в used manifest и ошибочно попадали в archive comparison. Теперь фактические bindings/CreatedAt двух строго ограниченных auxiliary paths проверяются при resume. PG/SQLite нельзя замаскировать как auxiliary. Содержимое volumes не переносилось/не удалялось; каждое historical baseline значение по-прежнему сравнивается строго.
4. Новые harness ошибки: PG ACK digest оказался BODY, не wire; browser ожидал raw phase вместо существующего русского UI текста. Исправлены проверки, а не протокол/UI evidence. Первый Python /tmp import-path issue и failed harness/audit logs сохранены. Ранние failures не выданы за successful tests.

Smoke соблюдает2s administrative limit явно, не полагаясь на медленный запуск диагностического контейнера. Длительность ожидания не включается в request→effective latency.

## Регрессия, безопасность и сохранность

Baseline: **1049 passed,0 skipped,53.91s,exit0** на отдельных реальных PG/Mongo. Финал: **1057 passed,0 skipped,56.55s,exit0**, восемь новых guard cases. Отдельный real `stage16_final_demo_smoke`, browser/fault/security probes не выдаются за дополнительные pytest cases. Старые tests/expected values не удалены. Сохранены Ascon/AES/Kuz KAT, nonce/replay, TLS/HMAC/manual control/effective, Outbox/Mongo, Policy13 traces/throughput, Stage14 oracle/frozen lifecycle, Shadow feature/model/no-control contracts.

Реальные TLS/ACL/password/untrusted-CA/replay negatives прошли. Повреждённый tag actual ciphertext дал rejected+1, identity осталась single. Forged/malformed/expired control/ACK не создал нового effective. Actual PG queries: ML models/events0, Policy applied0, transition actors только admin. Отдельный [receipt reconciliation](reports/stage16/receipt-reconciliation.json) сопоставил каждую receipt с Outbox/Mongo identity, wire profile, epoch/sequence/key reference и replay/SQLite authority. Shadow/Policy не имеют разрешённого автоматического control channel; `trusted_detector=false`, `Policy DRY_RUN`, `MANUAL_AUTHORIZED_CONTROL` сохранены. Ascon/AES проверены live в Stage16; Kuz KAT/regression и lab-only gates сохранены, нового live Kuz запуска Stage16 не заявляет. Magma not live; unknown Kuz backend fail closed.

Preservation: **1533 protected tracked files и6080 private artifacts** совпали с baseline; старые PCAP/models/frozen plans/SQLite/keys/holdout markers и Docker projects/volumes сохранены. Newly added anonymous auxiliary volumes доказанно принадлежат только новым Stage16 containers; это additions, не historical changes. Старые SQL volumes не монтировались в новые проекты. Hash/metadata audit не является побайтовой проверкой всего SQL volume.

Security audit: 22 различных новых telemetry keys и18 HMAC keys, cross-device/algorithm/control/historical reuse не обнаружен; private permissions проверены. Проверены 2182 public paths, последние1000lines каждого из53 retained new containers и `/app` 2 application images. Scope ограничен этими данными, не всеми log/cache bytes. Old Stage14 artifact/test/marker hashes неизменны, fit/threshold changes0. [Security](reports/stage16/security-release-verified.json), [preservation](reports/stage16/preservation-final.json), [release gate](reports/stage16/release-gate.json).

## Готовность к курсовой

Подготовлены14 Stage16 документов (включая baseline audit),7 Mermaid исходников,15 final screenshots, source/image/command metadata и [единый JSON/CSV каталог](reports/stage16/evidence-catalog-final.json) со stage/unit/sample/conditions/limitations. Старые графики Stage12/13/14/15 связаны ссылками, исследования не перезапускались ради иллюстраций и несопоставимые среды не объединены в universal chart.

Научные ограничения обязательны: Stage14 packet RF recall≈49%, IF≈7.7%, только5positive holdout sessions; Stage15 IF254/375 FP на новой corroborated Normal выборке. Нет independent-host generalization, production IDS, physical IoT/ARM, HA, ГОСТ certification или whole-provider constant-time proof. Shadow scores не authenticated security verdict и не вероятность атаки. Полный [список A/B/C](STAGE16_KNOWN_LIMITATIONS.md).

**Программный комплекс готов к оформлению курсовой в статусе исследовательского прототипа.** Все Stage16 services остановлены с сохранением state. Для показа используйте `python -m scripts.stage16_demo resume` из подготовленного окружения и [runbook](STAGE16_DEMO_RUNBOOK.md). Этап17 не начинался: далее только текст, оформление существующих иллюстраций, презентация и подготовка защиты, без новых функций/обучения/алгоритмов.

# Этап 7.5b-fix — результаты независимой проверки

Baseline 3282557fcf8b435c21e19d4e7cbc8e6397932405; ветка
feature/mqtt-tls-ground-truth-hardening. Только корректирующий этап, не 7.5c.

## Выявленные дефекты

| Дефект | Что установлено |
|---|---|
| validate проверял hashes, но не каждую исходную метку | **Реально воспроизведено**: согласованная подмена normal→violation в копии обоих CSV с новыми hashes/counts принята старым validator; исправленный oracle отвергает |
| connection activity названа packet_audited | Реальная ошибка контракта; ACK/TLS record не доказанно вредоносный пакет |
| rate/pattern из названия и len(actions) | Реально отсутствовало независимое измерение. Новые normal-interval/малый count/retransmission/size-only cases не получают positive |
| ACL только по client ID; replay без timed prior accepted | Реальные пропущенные инварианты; новые stale ACL, epoch/sequence/time/missing accepted conflicts дают unknown |
| tamper из local flag+aggregate reject | Недостаточно для атрибуции; actor остаётся unknown, серверный reject анонимный |
| scientific_quality_available из двух флагов | Реальный дефект правила отчётности; ложного итогового RF benchmark на этом наборе не было — модели на нём не обучались |
| Broker session parser | На реальном QoS1 потерял события reconnect из-за endpoint в close line; затем health connection мешал привязать CONNACK5. Исправлено, повторено, добавлены regressions |
| Границы только по local lifecycle | Потенциально расширяемое окно; counterexample с broker close8/local close9 выявляет ошибку. V2.2 использует пересечение и отвергает nonfinite evidence |
| Идентичные features названы duplicates | Методология слишком консервативной очистки, не доказательство одинакового физического события |
| Shared condition seed между partitions | Реально 7/9/2 пересечения; это риск зависимости, **не доказанная передача того же пакета** между частями |

Clock accuracy, generalization, отсутствие shortcuts/злонамеренной coordinated
перезаписи всех journals владельцем стенда — остаются рисками, не доказанными
атаками и не устранёнными автоматически этим этапом.

## Реализация

- pcap_audit: независимое bounded чтение PCAP, проверка tshark export по record
  identity/tuple/sequence/stream/time/5 features; без payload decoding/whole-file RAM.
- labels_v2/dataset_v2: rules connection-evidence-v2.2, новая семантика connection/
  window, отдельные scenario/packet evidence/provenance/unknown.
- Точное копирование PCAP под новым capture ID не увеличивает число групп: обе
  реализации отклоняют такой источник; добавлен отдельный regression test.
- label_verification: отдельный oracle, не вызывает builder/mapper; per-row
  reconciliation и exact known subset. Логическое несоответствие обнаруживается
  даже при пересчитанных производных hashes/counts.
- broker_evidence/observer/orchestrator: timed session-bound broker events,
  read-only ciphertext digest witness без Ascon keys; source failure/watchdog
  останавливает только experiment. Receiver/outbox/crypto/Policy не переписаны.
- stand_state: timed authenticated PG records, read-only transaction; anonymous
  reject не получает device ID. Общая readonly MQTT роль web принадлежит только
  новому исследовательскому broker, credential не из рабочего приложения.
- research.experiment: explicit quality dimensions, scientific flag false для
  текущих источников; uncorroborated labels блокируют новый plan, legacy lab v1
  не разрешён для нового train. Старые отчёты/модели не изменены.

## Архив и новая версия

Исходный 75b-v1 **не изменился**, включая PCAP/CSV/manifests/frozen plan и модели.
764 private file hashes проверены до/после; Git reports этапов 6/7.5b сохранены.
Legacy reconciliation воспроизводит старые правила, но не аттестует их научную
достоверность: `historical_rule_reproduction_only`.

Новая переразметка: `.local-runtime/ground-truth-fix/archive-v2.2/`, parent dataset
hash записан в manifest и label-changes. Физически сверены 59 captures/46395 rows.
**33848**старых known labels перешли в unknown;12547 уже были unknown;
итого**46395 unknown**, новых verified rows0. Причина — старые aggregate journals
не содержат независимых session/time/digest records. Их нельзя восстановить
задним числом из собственного намерения генератора. Для нового ML пригодных
подтверждённых групп в этом архиве 0. Старый план сохранён read-only; нового нет.

## Новая реальная проверка стенда

Новый project lcm-stage7b-gtfix с новыми volumes/credentials и отдельный
lcm-stage7b-gtfix-reg для regressions. Старые DB volumes не подключались.
Все ограничения TLS/Ascon/v2/ACL/replay/CPU/RAM/disk/watchdog сохранены; observer
отдельный keyless TLS client, а не отключение TLS или server-side decrypt proxy.

Финальный проверенный небольшой набор:9 отдельных captures,2269TCP observations:
1509 normal,190controlled_violation,570 unknown.39 corroborated connections;
positive относятся всего к 5 connections, **не к 190 независимым атакам**.
Три первоначальные proof-only iterations сохранены отдельно; в final dataset
нет неуспешных collector/observer runs. Statistical independence разных хостов/
устройств этим не подтверждена. Данные не объединены с внешними datasets.

| Реальный probe | Результат |
|---|---|
| A normal TLS→PG/outbox/Mongo+PCAP |211 normal rows в regular capture, no violation;1078 Mongo=PGoutbox на момент probe, pending0 |
| B controlled scenarios |5 positive connections; normal neighbours не унаследовали метку; bad auth identity пустая; tamper actor unknown |
| C forged generator intent |При неизменном broker outcome целевое соединение unknown |
| C mismatched independent digest |Replay не подтверждён, unknown |
| C coherent derived CSV tamper |Новые hashes согласованы, отвергнуто именно ground_truth reconciliation |
| D real QoS1 |4 broker DUP1 events,0 attack rows |
| E missing journal copy |Полный unknown, не fake normal |
| E live observer process stopped |Experiment aborted, verified dataset не создан;16 принятых сообщений дошли вMongo |
| F collector stop |Clients stopped2.158s,17 новыхMongo records, established publisher sockets0, partial capture excluded |

Дополнительные private-copy probes на **реальном** replay/ACL capture:
wrong epoch, wrong sequence, accepted time после replay, отсутствующий accepted,
ACL event вне session window. Во всех 5 cases actor unknown. Оригинальные journals
и работающие БД при этих вмешательствах не менялись.

Machine evidence: reports/stage75b-fix-integration.json/.txt,
reconciliation.json, real-evidence-negatives.json, data-quality.json,
label-changes.json. Label accuracy числом не оценена: внешнего gold standard нет.
Успешный oracle проверяет непротиворечивость и заданные инварианты, не 100%истину.

## Mutation и negative tests

Все 9 требуемых вмешательств (оба направления known labels, unknown promotion,
missing/extra row, connection/reason/capture/time) плюс подмена packet_id проверены
при согласованных производных SHA/counts. Проверяются конкретные diagnostics,
а не любой случайный exception. Raw source stream spoof с новым export hash
отвергается PCAP oracle. Reconciliation не меняет source/derived bytes.

| Injected defect | Target test | Expected / observed |
|---|---|---|
| Ignore broker auth code | generator_flag_cannot_replace_broker_result | false positive rejected by independent oracle; pytest1, killed |
| Remove missing-broker guard | absent_broker_source_makes_every_connection_unknown | baseline unknown processing fails; pytest1, killed |
| Attribute without SYN | no_syn_pipeline_cannot_attribute | corrupted builder rejected; pytest1, killed |
| Unknown→normal | no_syn_pipeline_cannot_attribute | unknown promotion rejected; pytest1, killed |
| Capture-wide violation | public_pipeline_positive_mixed_and_unknown | normal neighbour/SYN mismatch; pytest1, killed |
| Skip source identity comparison | coherent_hash_tampering...[connection] | negative test no longer rejects; pytest1, killed |
| Wrong stream→connection binding | public_pipeline_positive_mixed_and_unknown | source binding mismatch; pytest1, killed |
| Scenario name replaces measured condition | unverified_behavior... | few/no-change cases fail; pytest1, killed |

8 code mutants killed по поведению, не SyntaxError/import failure. Перед ними
unmutated baseline обязан пройти. Temporary source copies, рабочая ветка не
мутировалась во время full regression. Initial narrow broker target survived:
coverage gap исправлен explicit no-source test; initial report сохранён.
Fixture-edit NameError не засчитан как killed mutant; добавлен baseline preflight.

Новые unit PCAP — искусственные protocol-shaped bytes, не настоящий MQTT/TLS;
broker/PG journals в них fixtures. Они проверяют программу, не real attack metrics.
Настоящая сеть/БД/побочные эффекты проверены отдельным integration probe.
Подробный тест-аудит: RESEARCH_TEST_AUDIT.md.

## Coverage и неизменённый split

Автоматический aggregate audit без model.predict, threshold tuning или чтения
модельных ответов holdout. Старый compose и frozen split НЕ заменялись.

| Сценарий | Runs | Runs с positive v1 | Unknown | Normal | Positive до purge | Positive train/validation/test после purge |
|---|---:|---:|---:|---:|---:|---|
| bad_credentials |5|4|546|2809|10|3/0/1|
| forbidden_acl |5|5|1055|2613|28|3/4/1|
| replay |5|5|894|1704|151|28/18/0|
| tampered |5|5|784|4164|257|53/16/15|
| bounded_rate |5|5|745|1893|354|74/0/43|
| pattern_change |5|5|998|2004|147|32/19/0|

Это **исторические operational labels**, не независимо validated positives.
Test не содержит positive replay/pattern_change; validation не содержит positive
bad_credentials/bounded_rate. Нельзя заявлять оценку этих сценариев там, где их нет.
Полные per-partition before/after rows/connections/sessions/unique vectors/runs —
reports/stage75b-fix-coverage.json.

Purge удаляет одинаковые значения 5 features, а не доказанные одинаковые wire events.
Repeated packet_id0, но это не доказательство отсутствия duplicate wire capture;
physical_wire_duplicate_count неизвестен. Ordinary QoS/replay — отдельные сетевые
события.76producer-reported QoS DUP и 42deliberate replay actions в v1 не стали
задним числом независимым доказательством; в новом probe4 DUP подтверждены брокером.

23086 known rows удалено (68.2%); positives947→310, normal32901→10452. Старые
train/validation/test по-прежнему 6452/193,2025/57,1975/60; captures36/12/11 не
потеряны. Prevalence before→after: train2.7934→2.9044%, validation2.5136→2.7378%,
test3.1042→2.9484%. Condition seed intersections7/9/2 между парами частей показывают
ограничение capture-only split. Альтернативный split не внедрён молча; нужен
отдельно согласованный condition/device/host grouping с regression checks.

## Проверки и готовность

Full current pytest:**337 passed**, без skips, новые собственные PG/Mongo;
301 прежний тест +36 новых. Old synthetic regression tests обучают tiny fixture
RF/IF, это не обучение на IoT dataset и не научный benchmark. Real RF/IF на
старом/новом собственном наборе не обучались, final ML holdout не запускался.

Storage outage/crash/restart, ML missing-model/reload/Mongo recovery, Policy
parallel/restart/PG outage, trusted/untrusted CA/password/ACL, Flask roles/CSRF/
Socket.IO/safe redirect и Chromium12XSS probes прошли. Команды/exit codes —
reports/stage75b-fix-tests/storage/ml/policy/security/web/browser/unit*.txt.
Ruff и known-secret/image audit записаны отдельно после финальных проверок.

Оба новых plan gates вернули **exit2**, без файлов плана:
archive — нет independently corroborated labels; live — class capture support
normal9/violation5 при требуемых≥15 глобально/≥5 на часть. Пороги не ослаблены,
oversampling/дублирование captures не использованы. Old plan SHA и indices
не изменены. Данных для 7.5c **пока недостаточно**.

Доступны архив для reproduction/диагностики, новая unknown-only reannotation и
малый connection/window-labelled real probe dataset. Нужно собрать достаточно
независимо подтверждённых groups по всем нужным сценариям, согласовать будущую
методику split/единицу оценки и внешний источник/label audit. Для tamper нужен
независимый receiver-level authenticated digest/failure correlation; без него
нельзя объявить пакетную атаку установленной. Broker log latency/clock accuracy,
общий host/stack, external transfer и absence of shortcuts остаются ограничениями.
CPU/RAM quotas жёсткие; disk watchdog — бюджет, не filesystem hard quota.

Ни Policy Engine, ни crypto/security channel, ни исходные DB volumes не изменены.
Ascon-AEAD128/TLS/v2/replay/DRY_RUN/trusted_detector=false сохранены. Push/merge/
изменений main нет. Полный список файлов и итоговый Git hash — в финальном отчёте.

Оба созданных исследовательских Compose project остановлены без удаления volumes.
Проверены 764 архивных файла и 111 исторических Git-отчётов: изменений нет.
Полный список изменённых файлов: reports/stage75b-fix-files.txt.

## Команды и exit codes

Для реальных regression probes использовался только новый project из
`.local-runtime/ground-truth-fix/regression/compose.env`; `COMPOSE_FILE=compose.yaml:compose.research.yaml`.
Полные команды, время и фактический вывод сохранены в соответствующих `.txt` отчётах.

| Команда / проверка | Exit code | Фактический результат |
|---|---:|---|
| `docker compose --env-file .local-runtime/ground-truth-fix/regression/compose.env run --rm tests` | 0 | 337 passed, 30.84 s |
| `.venv/bin/python -m pytest -q tests/test_ground_truth_hardening.py tests/test_research_stand.py tests/test_research75.py` | 0 | 82 passed, 2.71 s; смесь synthetic fixtures, mocks и library calls |
| `.venv/bin/python scripts/mutate_ground_truth.py --output docs/reports/stage75b-fix-mutations.json` | 0 | Baseline passed, 8/8 behavioral mutants killed в temporary copies |
| `.venv/bin/python -m scripts.verify_ground_truth_hardening --env-file .local-runtime/ground-truth-fix/lab/compose.env --captures .local-runtime/ground-truth-fix/corroborated-captures --output .local-runtime/ground-truth-fix/integration-v22` | 0 | Реальные A–F, network/DB/capture/fault side effects |
| `python3 scripts/check_dual_database.py --env-file .local-runtime/ground-truth-fix/regression/compose.env` | 0 | Mongo outage/recovery, relay crash/restart, migration/data preservation |
| `python3 scripts/check_ml_system.py --env-file .local-runtime/ground-truth-fix/regression/compose.env` | 0 | Прежняя DEMO модель, missing/reload/dedupe/Mongo recovery |
| `python3 scripts/check_policy_system.py --env-file .local-runtime/ground-truth-fix/regression/compose.env` | 0 | Concurrency/restart/PG outage, DRY_RUN, applied=0 |
| `scripts.mqtt_security_smoke` в tests container | 0 | TLS trust, wrong password, ACL |
| `scripts.live_web_smoke` в tests container, `WEB_EXPECT_ML=1` | 0 | Роли, CSRF, Socket.IO, redirect, history, ML/Policy |
| `scripts/check_dom_xss.py` через Playwright/Chromium | 0 | 12 browser probes |
| Public `src.research_stand.dataset validate` для archive-v2.2 и live-v2.2 с исходными captures | 0 / 0 | Независимая reconciliation, files_modified=false |
| `src.classifier.research.cli plan` для обоих новых наборов | 2 / 2 | Ожидаемый quality/support отказ, plan не создан; не ML test |
| `.venv/bin/ruff check src tests scripts` | 0 | All checks passed |
| `scripts/audit_security.py` с четырьмя private dirs и тремя образами | 0 | Known-secret scan, permissions, image exclusions; не гарантия поиска неизвестных секретов |

Промежуточные меньшие pytest counts в append-only журналах относятся к предыдущим
коммитам этого исправления. Финальный результат — 337. Предыдущие неуспешные
mutation targets и изменения parser не скрыты, описаны выше и в machine reports.

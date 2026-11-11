# Stage 9 — результаты интеграции и демонстрации

## Версии и границы

Baseline: **d3cd219e39c719c6a53db057c58635f2b0410a8d**, исходная ветка
feature/adaptive-crypto-control-fix, исходное дерево чистое. Новая ветка:
**feature/system-integration-demo**. Runtime/presentation source:
**4ce8e33609d1b37dd6d445760a3d6265bedf864a**; заключительный host resume tool:
**b18db3f**. Последующий documentation commit не меняет runtime.
Main остаётся c352d817386a17fb244d3567b287af0412eed4e4. Push/merge/rebase не выполнялись.

Окружение: Linux x86_64, Docker Engine 29.9.2, Python 3.12.16, Flask 3.1.3,
cryptography 50.0.2, OpenSSL 3.0.22, Playwright 1.56.0 / настоящий Chromium.
Images/digests, quotas, source hashes: [runtime-isolation.json](reports/stage9/runtime-isolation.json).
Все эксперименты только в новых projects `lcm-stage9-demo-20261111` и
`lcm-stage9-demo-clean` с независимыми credentials/volumes/networks, по 3 software
agents. Физические Raspberry Pi, production deployment и live network IDS не заявлены.

## Что изменено

До этапа: dashboard объединял device telemetry в process-local buffer, имел
исходно зелёный MQTT indicator; Policy/Control показывали большие JSON без удобного
пути от request к receipt. Control требовал вручную ввести identity и не имел
явного confirmation UX. Источники и freshness были разрозненны.

Теперь `/`/`/monitoring` и `/control` открывают один inventory/dashboard;
`/devices/<device>` — карточка с PG admission, Mongo history/native charts,
security facts, Policy/risk/freshness, ML boundaries, capability picker и
сохранённой историей commands/ACK/audit/effective evidence. Навигация/основной UI
работают без CDN. Таблицы и IDs ограничены/сворачиваются, история paginated.

Переиспользованы `/api/telemetry/history`, `/api/control/<device>/switch`,
`/api/control/<device>/reconcile`; старые `/policy`/`/ml`/`/telemetry` и diagnostic
APIs сохранены. Два новых read-only shapes `/api/monitoring` и
`/api/monitoring/<device>` понадобились для согласованного inventory/status snapshot
без N+1 и без raw control bodies. Mutating APIs не дублировались.

Аддитивная миграция 0009 добавляет только диагностический receiver heartbeat.
Crypto/control/replay/Outbox/effective authority и предыдущие migrations не менялись.
Flask connect/pool timeouts ограничены. Shared installer поддерживает registry без
legacy identities; shared prepare выделен в функцию для безопасного reuse.
Новые prepare/run/check/browser/resume/mutation scripts обеспечивают воспроизведение.
Полный список файлов: [changed-files.txt](reports/stage9/changed-files.txt).

## Источники значимых статусов

* Provisioned/enabled/epoch: PG telemetry_devices; это не MQTT presence.
* Recent: последняя current-epoch PG Outbox admission ≤15 s. Temperature/humidity,
  measured_at/received_at/event/sequence из той же identity. Статусы stale/unknown/
  disabled различаются; future timestamps не считаются свежими.
* History: существующий Mongo API, device filter, limit 50/offset≤10000; timezone
  преобразуется browser-local↔UTC. Пропуски не подменяются нулями; Mongo failure
  показывает «История временно недоступна», PG facts продолжают отображаться.
* Verified effective: matching durable PG receipt + control device/epoch/profile.
  Device reported/ACK и requested/pending отдельно; 202 никогда не означает успех.
* Receiver: connected+SUBACK diagnostic heartbeat, TTL 10 s. Control/Policy:
  существующие PG heartbeat records, TTL 10/30 s. Container running не health.
* Policy: active version states/decisions/signals, DRY_RUN, отдельная recommendation
  и evidence freshness. Нет automatic bridge в control; admin выбирает target
  независимо от risk, с учётом capabilities/контекста, не условной «силы AEAD».
* ML: explicit demo disabled configuration и registry/results при наличии.
  RESEARCH/DEMO, trusted_detector=false; missing score не норма, score не attack
  probability. Исследовательский/production RF/IF training не запускался, frozen
  holdout не оценивался. Старые synthetic test fits в tmp сохранены как regression.

Матрица authority/limits: [STAGE9_SYSTEM_ARCHITECTURE.md](STAGE9_SYSTEM_ARCHITECTURE.md).

## Настоящий пользовательский и инфраструктурный E2E

[e2e-final.json](reports/stage9/e2e-final.json),
[e2e-final-browser.json](reports/stage9/e2e-final-browser.json), **exit 0**:

* Viewer login → 3 devices → alpha card → реальные Mongo values/Policy → switch
  control отсутствует → настоящий POST logout. Admin login → capability target →
  confirmation dialog → HTTP request → настоящие HMAC PREPARE/ACTIVATE → реальные
  device ACK → новая AES telemetry → PG effective receipt → Mongo. Обратный переход
  Ascon, timeline и reload. Beta/gamma остаются Ascon; gamma AES не поддерживает.
* В прошедшем полном browser прогоне **2 реальных перехода**, по настоящим PG/Mongo
  records. До него harness-прогон успел выполнить ещё 2 реальных перехода и все
  service fault checks, но упал на fixture callback; он не засчитан как полный E2E.
* Viewer/operator switch 403, missing CSRF 400, unknown device 404, unsupported
  gamma/unknown target 409. Никаких новых commands от Policy без admin action.
* Реальные остановки Mongo, Control, Policy, alpha, PG, broker и worker restart:
  history unavailable, receiver независим от auxiliary workers; stale heartbeat/
  telemetry обозначены; PG failure очищает current browser state, не показывает
  cached effective как актуальный. После восстановления UI читает authority заново.
* Настоящие TLS/HMAC/ACL negatives: incorrect MAC/key/topic/TTL/replay, malformed
  commands/ACK, contradictory ACK не меняют effective. Устройство продолжает
  telemetry, SQLite ledger не применяется к malformed command.
* Browser DOM: audit reason, ML score/model text, malformed API, чужой/spoofed
  device identity, HTML/attribute/script injection; все данные через безопасный DOM.
  Controlled API fixtures явно отделены от real switching; они не fake demo data.
* 1366×900 и 390×844, без внешних CDN; ошибок pageerror нет. История/команды не
  выдаются за confirmed до receipt, stale данные не изображают fresh presence.

Полный browser E2E выполнялся на c260aff; последующий 4ce8e33 меняет только
формат recommendation/порядок отображения timeline. Последняя presentation версия
проверена DOM assertions/mutations, real-data screenshots, source hashes и полным
715-test suite; дополнительные crypto switches ради косметического изменения
не подставлялись в отчёт.

Снимки последнего UI: [overview](reports/stage9/overview-final.png),
[alpha](reports/stage9/device-alpha-final.png),
[mobile](reports/stage9/device-alpha-mobile-final.png).
Они сняты с реального стенда после resume, без fixture substitutions.

## Повтор старых криптографических/recovery проверок

* [recovery.json](reports/stage9/recovery.json): **9 real scenarios, exit 0** —
  device restart, stale SQLite restore, worker restart после PREPARE, lost ACTIVATE
  ACK, broker outage, PG outage после intent, PG outage после activation,
  grace expiry/reconciliation и missing SQLite. Ожидаемый agent/probe exit 1 при
  unavailable/missing state проверен; false effective/downgrade нет.
* [poison-ascon.json](reports/stage9/poison-ascon.json) и
  [poison-aes.json](reports/stage9/poison-aes.json): **по 17 malformed → 17 rejected,
  3 valid admissions, 1 duplicate replay**, exit 0. Replay/Outbox/Mongo/effective
  evidence не меняются от malformed; valid alpha и соседний beta приняты.
  Receiver не reconnect из-за poison в bounded ~11 s; явный persistent-session
  restart + 5 s не вызывает redelivery. Publisher PUBACK не засчитан за manual ACK.
* [resume.json](reports/stage9/resume.json),
  [resume-primary.json](reports/stage9/resume-primary.json): полный stop/start
  обоих проектов, **exit 0**. Private material, command sequence, effective event/
  profile сохраняются; новый boot range у каждого из трёх devices строго выше
  прежней reservation. Root provisioning не сбрасывает existing SQLite/counters.
* Чистый запуск второго проекта прошёл `prepare_stage9_demo` +
  `run_stage9_demo start --build` без ручной коррекции volumes. Новый bootstrap
  имеет private files, stdin account transfer и used-volume guard.

## Regression и mutations

[regression-presentation-final.txt](reports/stage9/regression-presentation-final.txt):
**715 passed, 0 skipped, exit 0, 36.64 s**. Сохранены все 703 baseline tests,
добавлены 12 monitoring/freshness/receipt/heartbeat/expiry checks. Прежние Ascon/AES
KAT, parser/poison/replay, PG/Mongo/Outbox, HMAC/control/ACK/recovery, RBAC/CSRF/
Socket.IO, Policy/ML contracts и Ground Truth v2.2 включены. Для новой аддитивной
таблицы обновлены только точные schema head/table-count expectations 0008→0009,
42→43; assertions не удалены. Предыдущие полные 715-pass журналы сохранены.

[mutations-final.json](reports/stage9/mutations-final.json): **8/8 behavioral kills**:
ACK как effective, viewer authorization bypass, stale как recent, Mongo outage
как available, research trust claim, cross-device result, expired как active,
research actor authorization. Baseline 0, каждый mutant exit 1.

[dom-mutations-final.json](reports/stage9/dom-mutations-final.json): **3/3 Chromium
behavioral kills** — ACK вместо effective, stale вместо recent, Mongo failure как
пустая корректная история. Проверялись реальные DOM assertions, baseline exit 0;
перехватывался только JS конкретной test page, deployed source не менялся.

[preserved-mutations.json](reports/stage9/preserved-mutations.json): прежние
**14/14 stage8/8-fix mutations** обнаружены. Итого **25 целевых дефектов**, каждый
обнаружен функциональным assertion/точным exception contract, а не SyntaxError,
import/dependency failure. JSON содержит injected defect, test, expected/actual,
exit code и behavioral detection. Число tests/mutations не доказательство IDS
качества или отсутствия всех security defects.

## Найденные ошибки и сохранённые неуспешные попытки

1. `startup.txt`, exit 1: installer ожидал raspb1/smoke в 3-device registry.
   Исправлен условный ACL/scoped key provisioning; отсутствующие identities не
   получили прав. Перед завершением interrupted initial setup SQL показал 0
   control devices/commands/telemetry; использованное состояние не сбрасывалось.
2. `startup-corrected.txt`, exit 1: host account files 0600 недоступны UID10001.
   Права не ослаблены; setup перешёл на stdin. Новый clean start/resume это проверяет.
3. `e2e-browser-initial.browser.txt`, exit 1: harness искал button вместо реального
   input submit login. Исправлен browser selector, не auth/CSRF.
4. `e2e-browser-retry.browser.txt`, exit 1: Playwright route callback получил Request
   вместо default fixture argument. Исправлена factory closure с одним route
   argument; null сериализуется корректно. До ошибки real switches/fault checks
   прошли, но прогон целиком не назван успешным.
5. Source/visual review: expired transition мог считаться active до worker cleanup;
   исправлен read interpretation, добавлен PG regression + mutation. Длинные IDs/
   JSON recommendation были неудобны; теперь структурированный текст, раскрытие
   evidence, bounded scroll, chronology. Runtime crypto logic не менялась.

## Измеримые итоги после quiescence

[shutdown.json](reports/stage9/shutdown.json), exit 0. В каждом проекте provisioned=3,
во время инфраструктурного snapshot реально запущено 3 agent processes; это не
physical MQTT presence. После остановки active publishers=0.

| Project | PG accepted | Managed Mongo | Pending Outbox | Transitions completed/total | Final unknown/failed | Authenticated ACK | Effective receipts |
|---|---:|---:|---:|---:|---:|---:|---:|
| lcm-stage9-demo-20261111 | 10025 | 10025 | 0 | 18/18 | 0 | 33 | 21 |
| lcm-stage9-demo-clean | 7938 | 7938 | 0 | 2/2 | 0 | 4 | 5 |

Итого **17963 admissions/deliveries**, **20 настоящих completed transitions**,
**37 ACK**, **26 receipts** (6 baseline + 20 switch confirmations). Меньше ACK,
чем 2 на каждый transition, объясняется намеренными lost-ACK scenarios; effective
подтверждалась новой telemetry, не выдуманным ACK. Финальные alpha/beta/gamma в обоих
проектах Ascon. В середине recovery наблюдался UNKNOWN_OUTCOME и bounded reconcile;
финальный 0 не означает, что uncertainty никогда не возникала.

Primary: replay=1, delivery_error/retry=6/6 после управляемых outages; clean:
replay=2, rejected=34. Эти наблюдения не названы атаками. Во время активной доставки
разница PG/Mongo не считалась потерей; equality проверена после остановки producers
и дренирования. Отдельные Mongo fixtures полных suites не являются main receiver
admissions и не смешивались с managed device counts.

## Сохранность / безопасность / остаточные ограничения

[preservation.json](reports/stage9/preservation.json): 265 historical reports,
87 protected source/migration files и 764 архивных private files без изменений;
все 19 прежних stage8-fix named volumes существуют. Их содержимое заново не
хешировалось и не монтировалось: не заявляем неподтверждённый full-volume hash audit.
Новые projects не используют old volumes. Keys/PCAP/models/plans/benchmarks/frozen
holdout не менялись; scientific training/evaluation не проводились.

[secret-audit.txt](reports/stage9/secret-audit.txt): known legacy/current secrets
не найдены в Git/history/worktree/reports и 4 images, inputs 0700/files 0600.
[runtime-isolation.json](reports/stage9/runtime-isolation.json): actual limits,
networks/volumes/images и source hashes согласованы. Оба test projects остановлены,
все state/security volumes и private directories сохранены; `down -v` не выполнялся.

Остаются software/x86, bounded короткие окна, polling задержка, preprovisioned
keys, PREPARE-only/lost-state recovery limits, необходимость production TLS proxy/
backup/rotation и отдельной проверки реального hardware/масштаба. Полная история
component uptime/успешных Mongo probes не хранится. Нет доказанного live IDS,
автоматического ML control или обещания абсолютной доступности/защищённости.

## Точное воспроизведение и следующий этап

[STAGE9_DEMO_RUNBOOK.md](STAGE9_DEMO_RUNBOOK.md) — clean prerequisites, fresh
credentials/build/migrations/start, private admin login, scenes A–G, stop/resume и
ошибки. Например:

```bash
uv sync --frozen --group dev
.venv/bin/python -m scripts.prepare_stage9_demo --directory /tmp/lcm-stage9-demo-example --project lcm-stage9-demo-example
.venv/bin/python -m scripts.run_stage9_demo --directory /tmp/lcm-stage9-demo-example start --build
.venv/bin/python -m scripts.check_stage9_demo --directory /tmp/lcm-stage9-demo-example --output /tmp/stage9-check.json --browser
.venv/bin/python -m scripts.run_stage9_demo --directory /tmp/lcm-stage9-demo-example stop
.venv/bin/python -m scripts.run_stage9_demo --directory /tmp/lcm-stage9-demo-example start
```

Полные commands/exit codes/hashes — [manifest.json](reports/stage9/manifest.json),
вложенные command arrays E2E/browser/resume/shutdown и raw logs. Одноразовые
аудитные helper sources сохранены как `reports/stage9/reproduce-*.py.txt`; при
повторе восстановить их в указанные manifest `/tmp/stage9-*.py` paths. Они не
содержат secrets и не требуются для обычного prepare/start/demo/stop. Final Git SHA
документационного коммита сообщён в итоговом ответе; этот файл не содержит cyclic
self-referencing commit hash.

Логичный следующий этап 10: отдельно согласовать physical Raspberry Pi/hardware
integration и эксплуатационный deployment (TLS proxy, backup/restore/rotation,
retention/query scaling, performance/energy measurements). Научную проверку IDS
планировать отдельно при пригодных данных. Этапы 10 и 7.5c здесь не начаты.

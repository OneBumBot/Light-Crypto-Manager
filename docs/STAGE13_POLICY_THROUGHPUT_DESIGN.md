# Policy throughput design

Stage12 source baseline649a80f, original882 tests pass. No changes to pure FSM/rules/ML trust or cryptographic primitives. Migration0011 adds pending discovery, singleton persisted fairness and worker diagnostic metadata; historical migrations untouched.

Source INSERT/security and non-processing ML INSERT/UPDATE append a small identity+snapshot to policy_pending atomically, ON CONFLICT DO NOTHING. No active-version lookup, policy lock, source high-water, network service or memory-only queue on admission. Source provenance remains the journal/ML adapter; no claimed rejected MQTT identity gains binding. Pending row presence means work awaiting the active version; completed identity authority remains policy_signals(event_id,version), not a new cursor. Consumed rows are removed in the same transaction as state/decision/transition/proposal and persisted fairness turn. Missing schedule authority fails, never silently resets.

Install/activation seeds retained sources missing the selected version's marker; it is the only full anti-join path. Worker runtime selects indexed pending≤32 per source and processes≤32 source entries, alternating sources with fallback. A transaction holds the existing policy install advisory lock, loads one active version and parses one immutable Rules object. Each event still obtains its own server evaluation clock and calls the same state/evaluate logic; no batch-wide synthetic evaluation time. Parsed rules context is transaction-local and version checked. State row locking, guard/cooldown, idempotency tombstone, uniqueness constraints, immutable audit and proposal-only semantics remain.

Main waits10ms after work and1s at idle/error. No busy-loop when unavailable. Runtime maintenance cadence5s, at most one synthetic event, bounded128 candidates/proposals. Stale detection excludes devices with pending committed real items; other devices' backlog cannot prevent their stale diagnosis. Expiry does not acknowledge/apply a proposal. Retention and activation share serialization; an unread source-delete guard supplements consumed-only prune.

Multiple processes are supported only as serialized attempts, not sharded throughput. Tests cover2/4 workers and direct state row locks. Production stand uses one worker,1CPU/256MiB unchanged. Global mutex trades horizontal scaling for a clear ordering contract; future sharding is not implemented here.

Memory bounded by source batch payloads and existing FSM evidence caps. Durable pending disk follows retained source/status identities; no unbounded in-memory preload and no independent silent overflow/drop. Security journal retained capacity100000 remains explicit and includes consumed history until reviewed retention; processing faster is not automatic retention. ML source retention behavior is preserved; no promise that a pending queue supplies infinite storage. Benchmarks have message/time/disk/RAM/backlog stop conditions.

Provider/Kuz release change is only explicit Stage13 test-lab namespace authorization with existing APP_ENV/authorization/KAT gates. Production eligibility remains false. Magma, packet fields, keys/nonce/HMAC/replay/control workers are unchanged.

Read-model additions never promote a stale recommendation: the policy overview annotates authenticated telemetry age separately from recent ML/state writes, filters only the active version and labels stale/unavailable recommendations. Source processing lag, oldest pending age, evidence age and technical heartbeat are distinct. On API error the browser clears prior JSON/status and uses bounded no-store/same-origin requests. No new crypto apply UI or framework.

A lab-only receiver timing facade delegates to the real engine.begin() and preserves/rethrows all original results/exceptions. Its short matched25-device series measures actual monotonic checkout/SQL/commit exit, separately from the much longer main throughput runs. It does not replace decryption, admission, replay, source capture or manual ACK. These measurements are not inferred from the pre-transaction created_at field.

## Воспроизведение и безопасная остановка

Нужны Docker/Compose, Python project venv и зависимости проекта. Собирать original controller можно `python -m scripts.build_policy13_baseline --image-prefix lcm-stage13-policy-baseline-reference`; инструмент экспортирует Git baseline во временный каталог и добавляет только изолированный installer, не переключая checkout. Этот отдельный convenience builder добавлен после основных измерений; точные фактически использованные build/log/image IDs сохранены в raw reports.

Для нового оптимизированного run сначала собрать текущие runtime/tests с отдельными тегами:

```bash
docker build --target runtime -t lcm-stage13-policy-current-runtime .
docker build --target tests -t lcm-stage13-policy-current-tests .
.venv/bin/python -m scripts.run_policy13_experiment \
  --variant optimized --devices 25 --seconds 300 \
  --runtime-image lcm-stage13-policy-current-runtime \
  --tests-image lcm-stage13-policy-current-tests \
  --directory .local-runtime/stage13/new25 \
  --output docs/reports/stage13/new25r1 \
  --project lcm-stage13-policy-new25
```

Для baseline указать original runtime/tests; не подставлять текущий код под baseline label. Одновременно не запускать другие cohorts. Инструмент требует новые directory/project, проверяет активный Stage13 alpha, сохраняет IDs и останавливает сервисы после bounded observation/drain. При исключении проверить собственный project и выполнить `.venv/bin/python -m scripts.policy_lab stop --directory .local-runtime/stage13/new25`. Никогда не удалять volumes/keys, не копировать старые SQLite в новый cohort. `start` существующего стенда продолжает durable state и проверяет used volumes; это не новый независимый experimental run.

Снимки/сверка: `python -m scripts.policy13_collect_runs`, затем `python -m scripts.policy13_analyze`, `MPLCONFIGDIR=/tmp/lcm-policy13-mpl python -m scripts.plot_policy13`. Collector работает только с остановленными свежими Stage13 performance projects, временно запускает их PG/Mongo для read-only census и снова останавливает. Хранилища прежних этапов не используются. После archival больших JSON скрипты анализа читают `.json.gz` без изменения байтов исходных записей.

Если Docker address pools исчерпаны, не применять prune: выбрать проверенную непересекающуюся подсеть, задать `networks.default.ipam.config[].subnet` только в новом приватном Compose override и сохранить её в config provenance. В фактическом продолжении применены10.213.1–5.0/24; это не обещание, что они свободны на другом хосте. Пароли находятся в приватных `accounts/*.password`, не в отчёте; web доступен только через loopback dynamic port.

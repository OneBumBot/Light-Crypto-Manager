# Commands, exit codes and provenance

Baseline source: `20d298cc3b48f14920a00e9403bdaf0ff7e38c5a`. Final application validation: `bf8c7d5bfa84ed6120e0174c2b7500dc1da04af6`; immutable-original benchmark instrument: `5d49ddfeecd799daf15a9ae8ee50fcb6dbdba592`; evidence/plot tools: `3f477e0` or later. No raw source SHA was retroactively invented. JSON that recorded source_sha retains its own value; raw logs without that field are linked by file hash, test name and validation context in evidence-index.json. Nested `commands` arrays in system/fault/browser/final reports contain actual argv, start/finish times and individual exits. This file provides replay commands and observed top-level outcomes, not an invented complete shell-history transcript.

Run from repository root with the project's compatible `.venv`, Docker Compose/Go/Chromium installed. Private path below was `.local-runtime/stage12/lab`, project `lcm-stage12-crypto-research-lab`. New experiments require a fresh suffix/directory; do not overwrite immutable output JSON. Example commands below use `/tmp` output paths for replay; committed reports retain their original names.

```bash
.venv/bin/python -m scripts.crypto_research_lab prepare --directory .local-runtime/stage12/new --project lcm-stage12-crypto-research-new
.venv/bin/python -m scripts.crypto_research_lab start --directory .local-runtime/stage12/new --build
```

Both lifecycle commands: exit0. Existing manifest start resumes keys/state, does not reprovision counters. Account usernames `demo-admin`, `demo-viewer`, `demo-operator`; passwords only in private `accounts/<role>.password`. UI loopback address is printed after real readiness checks. Do not copy passwords into commands/reports. Policy DRY_RUN and manual control are required.

Tests used the Compose `tests` service with real lab PostgreSQL/Mongo:

```bash
.venv/bin/python - <<'PY'
from scripts.crypto_research_lab import Lab
lab=Lab('.local-runtime/stage12/lab')
r=lab.run('run','--rm','-T','--no-deps','tests',timeout=180)
print(r.stdout)
print(r.stderr)
raise SystemExit(r.returncode)
PY
```

| Evidence | Actual observed outcome | Exit |
|---|---|---:|
| baseline-regression.txt | 868 passed,0 skipped,37.33s; original runtime before edits | 0 |
| full-regression-first.txt | 881 passed before added EOF regression | 0 |
| full-regression-final.txt | 882 passed | 0 |
| regression-release.txt | 882 passed,0 skipped,42.00s after UI scope fix | 0 |
| persistent-kat-final.txt | 66 passed, KAT/dispatch/provider boundaries | 0 |
| worker-negatives-release.txt | 14 passed, bounded IPC failures/concurrency | 0 |
| stderr-eof-before.txt | intended behavioral failure before fix | 1 |
| mutations-release.json | baseline176 passed;25/25 behavioral mutants killed | runner0, each mutant1 |

Build `python -m scripts.build_kuz_provider --output <private new binary>` was run with pinned local Go sources/offline dependency resolution; two optimized builds matched, as did two original-source builds. Logs/hashes: repro-build-a/b.json, optimized-repro-build.json, optimized-repro-result.json. The original binary was built from preserved Stage11 native source, **not** inferred from the new executable's one-shot mode. Toolchain recorded in provider-build.json. Upstream `go test -json ./magma ./mgm`, key-schedule KAT and `go test -race` passed; raw JSONL retained. These public-vector tests do not enable Magma.

Candidate Python checkout used below: `.local-runtime/stage12/candidates/pygost-new` (exact path names may be changed for replay; revision must match candidates.json). Never pip-install it into runtime or register its wrapper as live crypto.

```bash
LCM_KUZ_PROVIDER=.local-runtime/stage12/optimized-provider LCM_KUZ_BACKEND=persistent .venv/bin/python -m scripts.python_kuz_research --candidate .local-runtime/stage12/candidates/pygost-new --output /tmp/python-crosscheck.json
.venv/bin/python -m scripts.magma_vectors_research --candidate .local-runtime/stage12/candidates/pygost-new --output /tmp/magma-vectors.json
.venv/bin/python -m scripts.magma_budget_research --output /tmp/magma-budget.json
```

Exit0 each:31 cross-checks/93 damaged tags/40 parameters; both RFC A.2 examples+RFC8891; exact rational budget grid. See Python reports for raw API findings. Candidate clone commands/pins are in candidates.json; official/archive HTTPS fetch failures returned curl60, not counted as cryptographic failures or bypassed with insecure TLS flags.

Real network command:

```bash
.venv/bin/python -m scripts.check_stage12_system --directory .local-runtime/stage12/lab --output /tmp/stage12-system.json
.venv/bin/python -m scripts.stage12_recovery --directory .local-runtime/stage12/lab --output /tmp/stage12-recovery.json
.venv/bin/python -m scripts.stage12_worker_recovery --directory .local-runtime/stage12/lab --output /tmp/stage12-worker-recovery.json
.venv/bin/python -m scripts.check_stage9_browser --directory .local-runtime/stage12/lab --output /tmp/stage12-browser.json
.venv/bin/python -m scripts.check_malformed_mqtt_recovery --env-file .local-runtime/stage12/lab/compose.env --profile kuznyechik-mgm-v1 --output /tmp/stage12-poison.json
```

All exit0. System5×60 reconciled identities; seven real-service faults; two real Go-child kills; Chromium real4 transitions plus separately marked DOM fixtures; poison19rejected/3accepted/1replay. The scripts have bounded execution; do not run fault tests concurrently with pytest or mutations against the same lab DB.

Stage11 harnesses were explicitly bound to the Stage12 Lab adapter, e.g.:

```bash
.venv/bin/python -c 'from scripts import check_kuz_control_browser as m; from scripts.crypto_research_lab import Lab; m.Lab=Lab; m.main()' --directory .local-runtime/stage12/lab --output /tmp/control-browser.json
.venv/bin/python -c 'from scripts import check_kuz_lostack as m; from scripts.crypto_research_lab import Lab; m.Lab=Lab; m.main()' --directory .local-runtime/stage12/lab --output /tmp/lost-ack.json
.venv/bin/python -c 'from scripts import check_kuz_sqlite_recovery as m; from scripts.crypto_research_lab import Lab; m.Lab=Lab; m.main()' --directory .local-runtime/stage12/lab --output /tmp/sqlite.json
```

Exit0 each. Control page4 actual transitions; two dropped ACTIVATE ACK scenarios, including explicit reconciliation; missing/stale SQLite refusal. Missing-state agent itself intentionally exited1, which was the expected behavior. `control_security_probe` was run inside tests service with private control mounts: actual TLS/HMAC/topic/device/keyref/schema/ACK/replay/ACL negatives, exit0, control-negatives.txt. No AckSimulator.

Mutations used `python -m scripts.stage12_mutations --output <new JSON>` inside the isolated test container with its `TEST_DATABASE_URL`, not a host production URL. Baseline tests pass before mutation;25 separate mutated behavioral failures exit1; runner0. Full commands/error tails are in mutations-release.json. No SyntaxError/ImportError counted.

After stopping the lab (state retained), benchmark commands used unique fresh outputs:

```bash
.venv/bin/python -m scripts.crypto_research_lab stop --directory .local-runtime/stage12/lab
LCM_KUZ_PROVIDER=.local-runtime/stage12/optimized-provider .venv/bin/python -m scripts.stage12_benchmark --candidate .local-runtime/stage12/candidates/pygost-new --output /tmp/micro.json
LCM_KUZ_PROVIDER=.local-runtime/stage12/optimized-provider .venv/bin/python -m scripts.stage12_benchmark --candidate .local-runtime/stage12/candidates/pygost-new --go-refresh --output /tmp/go-pair.json
LCM_KUZ_PROVIDER=.local-runtime/stage12/optimized-provider .venv/bin/python -m scripts.stage12_benchmark --candidate .local-runtime/stage12/candidates/pygost-new --cpu-only --output /tmp/cpu.json
LCM_KUZ_PROVIDER=.local-runtime/stage12/baseline-provider .venv/bin/python -m scripts.stage12_benchmark --candidate .local-runtime/stage12/candidates/pygost-new --only-one-shot --output /tmp/original.json
LCM_KUZ_PROVIDER=.local-runtime/stage12/baseline-provider .venv/bin/python -m scripts.stage12_benchmark --candidate .local-runtime/stage12/candidates/pygost-new --only-one-shot --cpu-only --output /tmp/original-cpu.json
```

Exit0 all. Actual report datasets:microbenchmark200,provider-refresh80,cpu-benchmark25,cpu-refresh10,original-one-shot40,original-one-shot-cpu5 runs. First matrix preceded EOF fix; final selections keep row-level provenance. `--go-refresh --cpu-only` produced the10 final paired CPU runs. Partial/progress files are checkpoints of those same runs, not extra samples.

Native measurement command: `python -m scripts.stage12_native --measure <private kuzmeasure binary> --original <original binary> --optimized <optimized binary> --output <new JSON>`, exit0. Binary built from native/kuzmeasure using the same pinned local dependency and offline Go settings. Five processes; direct native/keysetup, echoIPC, startup+reject and fixed/random timing classes. `go tool objdump -s 'github.com/tarantool/go-gostcrypto/mgm.*gfMul' <optimized binary>` exit0; actual branch preserved in gfmul-assembly.txt.

```bash
MPLCONFIGDIR=/tmp/lcm-stage12-mpl .venv/bin/python -m scripts.plot_stage12
.venv/bin/python -m scripts.index_stage12_evidence --directory .local-runtime/stage12/lab --output docs/reports/stage12/evidence-index.json
```

Plots exit0,10 measured PNG/SVG families+CSV. Final inventory exit0, reports/content hashes, full new-report secret scan, historical equality, zero running Stage12 containers. Earlier running-image/log/role/isolation audit exit0 in preservation.json. Final snapshot was captured after stopping publishers and draining before `stop`; stored commands in final.json include all final SQL/Mongo/usage probes. `down -v` was never run.

# Actual Stage13 command/evidence map

Repository baseline649a80ff7f7d66f72f5f483b384754ae594f221e; branchfeature/policy-engine-throughput-hardening. Main/push/merge/rebase untouched. Run from repository root with project venv and Docker/Compose. All private material is under `.local-runtime/stage13`, never in reports. Measurements identify the executed image/core hashes as well as host source SHA.

| Actual action | Evidence/exit |
|---|---|
| Original full PG/Mongo pytest in fresh base3 | baseline-regression.txt:882 passed,0 skipped,41.80s,exit0 |
| Red internal ML ValueError fault test | ml-fsm-failure-before.txt:exit1, legitimate source consumed incorrectly |
| Full final PG/Mongo pytest | full-regression-final.txt:922 passed,0 skipped,52.09s,exit0 |
| Golden fixed trace/upgrade evidence emitted by pytest | golden-release.json:13 equal traces; row hashes preserved |
| `python -m scripts.policy13_mutations --source-sha ...` in tests container | mutations-final.json/txt:24 behavior defects detected, baseline pass, runner0 |
| Private SQL scale EXPLAIN ANALYZE BUFFERS JSON | query-plans-before.json;1000/10000/50000/100000 rows; actual plan output |
| `python -m scripts.policy13_ablation` | ablation.json/txt:15 fresh-schema cases, exit0 |
| cached/uncached paired ablation | ablation-cache-control.json/txt:6 fresh schemas, exit0 |
| Original/optimized cohort runners | launch-baseline-matrix.py / launch-optimized-matrix.py, logs and per-run result.json commands/exits |
| Short receiver transaction wall series | launch-after-performance.py; per-run admission-timings.jsonl;2 complete pairs included |
| Independent census of stopped fresh cohorts | `python -m scripts.policy13_collect_runs`; ledger-final.json.gz, environment.json, actual-policy-plan.json, census-commands.json |
| `python -m scripts.policy13_analyze` | performance-summary.json/run-summary.csv:17 included runs,exit0; analysis-after-archive.txt verifies gzip replay |
| `MPLCONFIGDIR=/tmp/lcm-policy13-mpl python -m scripts.plot_policy13` | plots.txt/figures/:13 PNG/SVG families,exit0 |
| `python -m scripts.policy13_artifacts` | archival.txt/raw-archive.json:lossless compression of new Stage13 raw files,exit0 |
| Pinned browser prerequisite `uv pip install --python .venv/bin/python playwright==1.56.0`; `PLAYWRIGHT_BROWSERS_PATH=.local-runtime/stage13/browser-cache python -m playwright install chromium` | browser-dependency-install.txt:Chromium141.0.7390.37/build1194; project-private binaries |
| `PLAYWRIGHT_BROWSERS_PATH=.local-runtime/stage13/browser-cache python -m scripts.policy13_reliability --directory .local-runtime/stage13/crypto --output docs/reports/stage13/policy-reliability.json` | policy-reliability-console.txt and JSON on actual successful completion |
| `python -m scripts.policy13_crypto_checks --directory .local-runtime/stage13/crypto --reports docs/reports/stage13` | per-harness JSON/logs and crypto-final.json on actual successful completion |
| Historical file/private-state and secret scan | preservation-before.json, private-projects-before.json, preservation-after.json on successful final check |
| Image/log/network/quota audit | runtime-audit.json on successful final check |

`result.json.commands` and census/fault reports retain literal argv with actual exit codes, times and public paths. Private passwords/keys/config bodies are not argv/report fields. Application SQL hooks omit driver-internal pre-ping, server triggers and server-internal statements; actual DB statistics are separate. Hook commit event precedes DBAPI commit; actual receiver wall facade includes successful context exit.

Failed infrastructure attempts are retained: missing initial Docker COPY installer, metadata Git absence, output bind permissions, exhausted default network pools, missing Playwright, and interrupted recovery orchestration. They are not credited as mutation detection. `resume-console*.txt` and excluded/interrupted markers document them. A mistaken duplicate recovery controller was stopped; possibly overlapping short repeats are excluded conservatively. Main load cohorts completed before this and are unaffected. New resumed projects use explicit nonoverlapping10.213.x/24; historical networks/volumes were retained.

Historical Stage10/11/12 reports are not overwritten. No production/ARM/HA/IDS-effectiveness inference. Full final artifact hashes and source context are in artifact-index.json; it excludes itself. New raw JSON may be stored as `.json.gz`; decompressed SHA/raw byte length are recorded in raw-archive.json. Analysis supports both formats.

Completed real follow-up: policy-reliability.json exit0; crypto-browser/control-browser/lost-ack/crypto-service-recovery/poison/crypto-final exit0. Crypto console confirms lab stopped; actual commands/times remain inside each report. Final scanner uses exact byte fixed-string GNU grep under LC_ALL=C plus explicit LF/CR fallback (ripgrep pattern parser rejected arbitrary non-UTF8 test patterns).100 seeded comparisons with naive byte membership, including NUL/LF/CR, pass in secret-matcher-check.txt. This audit-tool verification is separate from922 application pytest tests. Audit implementation errors/overbroad environment assertion are retained in failed logs and are not credited as security mutation detections.

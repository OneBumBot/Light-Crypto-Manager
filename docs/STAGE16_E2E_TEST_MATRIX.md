# Stage16 — финальная матрица

| Проверка | Реальный результат | Источник |
|---|---|---|
| Fresh baseline PG/Mongo | 1049 passed, 0 skipped, exit0 | baseline-retry-pytest.txt / commands |
| Final PG/Mongo regression | 1057 passed, 0 skipped, exit0; 8 новых guard tests | regression-release-pytest.txt / commands |
| Main start + 3 Device Agents | Новые authenticated PG/Mongo identities перед ready | start-first.txt, aux-resume-first/second.txt |
| Admin Ascon↔AES | PREPARE/READY/ACTIVATE/ACK и новая committed AEAD receipt | smoke-aux-final.json, final-evidence-summary.json |
| Independent Beta/Gamma | Profiles/command sequence соседей не меняются | smoke-aux-final.json |
| Unsupported Gamma / roles / CSRF | 409 / viewer+operator403 / missing-CSRF400 | smoke-aux-final.json |
| PG→Outbox→Mongo | Exact identity set сравнен при quiescence, pending0 | smoke-aux-final.json / stopped checkpoint summary |
| Nonce/replay | Непересекающиеся boot ranges, replay не создаёт duplicate | stage16_security.json / final-evidence-summary.json |
| Wrong AEAD tag | rejected+1, identity remains single | stage16_security.json |
| Real HMAC/ACL negatives | Forged/malformed/expired control/ACK не меняет effective | control_security_probe.json |
| Policy DRY_RUN/no ML control | DB actors admin-only, applied0/models0/events0 | no-auto-control-final.json |
| Stop/resume | History/receipts/ledger/keys сохраняются; ranges новые | recovery.json / aux-resume-first/second.txt |
| Used-state refusal | Missing/replaced volumes, markers; auxiliary cannot disguise crypto state | recovery.json + 8 guard unit tests |
| Limited faults | Receiver/Mongo/PG/Device/Policy/control interruption | recovery.json |
| Desktop/mobile | 5 mobile pages390px без document overflow, JS errors0 | browser-final.json |
| Browser XSS | 4 payloads в legacy flows/ML/Policy, assertions passed | browser-xss.txt |
| Clean checkout latest code | New venv/keys/volumes/build/smoke/stop/resume, commands exit0 | release-clean-checkout-commands.json |
| Shadow IDS main demo | OPTIONAL_RESEARCH_DEMO_UNAVAILABLE, empty scores/source unavailable | browser-final.json / shadow-unavailable screenshot |
| Kuz/Magma gates | Stage16 Kuz authorization запрещена, unknown backend fail closed, Magma not live | security-release-verified.json |
| Preservation | Старые protected files/projects/volumes без изменений | preservation-final.json |

Основной реальный integration case — `stage16_final_demo_smoke` в scripts/stage16_smoke.py, вызывается единым runner. Это не pytest mock case; 8 новых pytest cases проверяют guards отдельно, не заменяют network E2E. Старые tests/expected values не удалены и не подогнаны. Полные baseline и финальные suites содержат Ascon/AES/Kuz KAT, nonce/replay, manual control/effective, Outbox/Mongo, Policy13 FSM/throughput, Stage14 oracle/frozen lifecycle и Shadow invariants.

Каталог находится в docs/reports/stage16/. Intermediate runs и first failed harness/audit outputs сохранены, но не засчитываются как successful release tests. Published checks относятся к их source SHA, actual image IDs и commands, а не к будущим версиям.

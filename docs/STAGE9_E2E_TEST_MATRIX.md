# Stage 9 — матрица проверок

Сводные факты, source commits, commands/exit codes — STAGE9_RESULTS.md и reports/stage9.

| Граница | Проверка | Реальный источник / что обнаруживает |
|---|---|---|
| Fresh/stale/disabled | test_monitoring + browser stopped agent | PG admission age; не provisioning presence |
| ACK/effective | PG test_snapshot_ack... + DOM mutation + real switch | новый receipt обязателен; reported не effective |
| Identity | scoped snapshot test + browser mismatch/XSS device | другой device не попадает в текущую карточку |
| Expiry | expired snapshot PG test | expired не active/success; read model не пишет FSM |
| Mongo failure | API PG test + real browser stop Mongo + DOM mutation | unavailable не пустая история; receiver независим |
| Worker failure | real browser stop control/policy | TTL stale, disabled switch, fresh telemetry отдельно |
| PG/broker failure | real browser fault + recovery probe | invalidate browser state, redelivery/commit semantics |
| RBAC/CSRF | actual HTTP viewer/operator/no token + preserved tests | explicit admin + same-session token required |
| Capabilities | gamma DOM + actual POST | unsupported AES не даёт command |
| HMAC/ACK/ACL | preserved real TLS control_security_probe | bad key/MAC/topic/type/ACK не меняет effective/SQLite |
| ML boundary | metadata/actor mutations + old ML/policy tests | trust false, research actor не авторизует control |
| Injection | actual Chromium controlled API fixtures | textContent/DOM; audit reason/ML score/device text не исполняются |
| History/chart | actual Mongo API + Chromium | timestamps/device filter/bounded pagination; no fabricated zero samples |
| End-to-end | viewer→admin→AES→Ascon→reload | настоящий browser, agents, ACK, telemetry, PG receipts, Mongo |
| Restart | runner stop/start + browser worker/device restarts | сохранность command/nonce/effective; новый range |
| Poison | reused real TLS bounded probe | reject audit/manual ACK; no new admission; next valid + receiver restart |
| Crypto/recovery | preserved full suite + extended real faults | Ascon/AES KAT, replay, lost ACK/grace/SQLite rollback |
| Schema | old migration tests + diagnostic heartbeat test | additive 0009, counters/evidence preserved; no heartbeat admission |
| Preservation | hashes/secret/image/isolation audit | нет изменений historical data/models/plans/keys/reports |

## Различение evidence

* Unit tests: exact states/errors, policy semantics, caller contracts.
* PG integration: actual transactions/AEAD/device SQLite, independent schemas.
* Mongo integration: actual authenticated reads/writes and permission checks.
* Browser E2E: actual visible DOM/user actions/confirmation plus actual service faults.
* Controlled DOM fixtures: явно отдельные injection/lying-status boundary checks,
  не доказательство работы MQTT или ML.
* Mutations: baseline обязателен, функциональное assertion failure; SyntaxError,
  imports/missing dependencies не считаются обнаружением.

Прежние 703 tests сохранены; 0009 требует обновить ровно ожидаемый table count
42→43 и schema head 0008→0009, не удалить assertions. Новый suite — 715 checks.
Полные research tests используют старые временные synthetic fixtures; научные
RF/IF experiments и frozen holdout не запускались/не изменялись.

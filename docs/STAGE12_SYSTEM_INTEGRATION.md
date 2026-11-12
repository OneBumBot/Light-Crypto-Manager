# Stage12 system integration

Algorithm/profile IDs remain Ascon/AES/Kuznyechik. Backend selection `LCM_KUZ_BACKEND=one-shot|persistent` is internal, exact and fail-closed; unknown value raises ProviderUnavailable. No Magma live descriptor. Existing HMAC v2/telemetry v2, key_reference, AAD/nonce checks, per-key PG authority, replay, Outbox and effective receipt path preserved. `src/kuz_release.py` explicitly permits the new Stage12 namespace only with the existing test/lab authorization flags; default production activation remains forbidden.

Registry metadata now distinguishes algorithm, implementation backends/status, cryptographic vectors, lab eligibility, production not-approved/not-assessed, device support, nonce and key lifetime requirements. No language-dependent user profile IDs. Existing UI reads the same authoritative monitoring/control/history APIs; admin/CSRF and capability filtering remain. Python/Magma research artifacts are not selectable profiles.

Reproducible fresh setup:

```bash
.venv/bin/python -m scripts.crypto_research_lab prepare --directory .local-runtime/stage12/new --project lcm-stage12-crypto-research-new
.venv/bin/python -m scripts.crypto_research_lab start --directory .local-runtime/stage12/new --build
.venv/bin/python -m scripts.check_stage12_system --directory .local-runtime/stage12/new --output /tmp/stage12-network.json
.venv/bin/python -m scripts.crypto_research_lab stop --directory .local-runtime/stage12/new
# Resume same keys/counters; no provisioning reset:
.venv/bin/python -m scripts.crypto_research_lab start --directory .local-runtime/stage12/new
```

Three software devices,1Hz. Alpha is measured under each target profile/backend; beta/gamma remain Ascon background, a declared constant workload rather than falsely labelled all-AES cohort. New directory/project required for new keys. Passwords in private accounts/admin.password etc, usernames demo-admin/viewer/operator; never copied into reports. Start applies existing migrations and additive strict Mongo profile validator, performs actual first telemetry checks and prints loopback UI URL. No down-v or state deletion. Go worker keys never in argv/env/log, only bounded private pipes; hard service cgroup limits inherited. CPU/RAM/log limits unchanged.

Static windows20s, actual source formed identities reconciled against PG and Mongo after delivery. Scheduled/publish/queued/PUBACK separated; PUBACK alone is broker evidence. Same-host wall clock, accuracy not independently measured; measured_at→receiver-created is not isolated network RTT or exact PG commit latency. All reports retain their sampling boundaries. Real-service recovery reuses the previous seven-fault harness with only Lab adapter changed to Stage12; no ACK simulator.

The implementation ID in the web descriptor reflects that web process's configured backend, not authenticated device implementation evidence. Mixed-backend research intentionally differs by component. The UI labels this scope explicitly; accepted AEAD verifies the algorithm, not the implementation language or process architecture of the sender. No synthetic device-backend status is introduced.

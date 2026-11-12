# Kuznyechik provider audit

Baseline20d298c, clean branch; Alembic0010 unchanged. Stage11 reports distinguish algorithm from pure Python Ascon/native AES/Go subprocess. Provider descriptor key32/nonce16/tag16; telemetryv2 AAD binding, per-key PG budget and boot grants remain authoritative. No nonce state moves into crypto worker.

One-shot does a process launch, package initialization, key schedule, MGM allocation and pipe copies for every encrypt/decrypt. Existing5s subprocess timeout and post-response4113B bound do not measure pure algorithm time. Native input is bounded before allocation; malformed status maps to infrastructure failure, bad tag to ValueError→InvalidTelemetry. Original `capture_output` buffers the trusted executable's output before checking bounds; a malicious/replaced executable is outside this trust assumption. Persistent protocol instead bounds response length before reading payload.

Selected optimization: optional bounded local worker, default remains one-shot. No sockets/listener, keys only stdin, exact ID/length-bound response, one outstanding request under a Python lock, fresh cipher/MGM per frame.256 requests/process,25s parent recycling/30s native lifetime; soft Go heap target32MiB plus inherited container memory/CPU cap. No cache of keys or contexts. Buffers cleared best effort; Go/Python copies and round keys are not guaranteed zeroized. This is not a hard standalone heap proof or side-channel audit.

Crash/timeout/protocol fault kills/reaps worker and fails current operation without retry/fallback; next caller can start a new worker. Device has already consumed sequence, so agent failure cannot silently reuse the ICN. Receiver infrastructure failure preserves no-ACK/redelivery semantics. Forked child closes inherited pipes without killing parent process, resets its lock and starts its own provider.

Actual initial KAT found path-caching bug: changing configured executable reused the old worker. Fixed by binding worker lifecycle to binary path; missing executable now fails closed. Existing authentication and key-usage logic unchanged.

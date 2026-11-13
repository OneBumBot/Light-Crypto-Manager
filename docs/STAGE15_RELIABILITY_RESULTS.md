# Reliability evidence — evolving report

Actual defect1: original model image did not contain Research Stand; importing offline risk helper produced ModuleNotFoundError at scoring. Records were INFERENCE_ERROR/null, not Normal. First series stopped and retained. Minimal scoring adapter now imports no training/oracle, exactly matches512original-formula comparisons on new packets; test_scoring_does_not_import_offline_training_or_oracle detects reintroduction.

Actual defect2: model worker crashed on SQLite database-is-locked in first25-deviceRF trial. Capture retained2544physical packets/kernel drops0, but application overflow1767; statusCAPTURE_INCOMPLETE. It is not a successful or lossless inference run. PG/Mongo continued authenticated telemetry. Failure raw DB/PCAP and stopped worker preserved. New bounded max64result batch commits signal+processed markers+session stats atomically, BEGINIMMEDIATE before work and at most6busy attempts with bounded backoff. Correctness tests hold a real competing SQLite writer, verify retry succeeds and rollback leaves no partial results/markers. No cap/memory/key/control protections disabled.

Additional context hardening: an earlier-timestamp new SYN cannot falsely start a complete generation; it becomes unavailable. Final parity gate repeated after extractor hash changed. Separate journal-only directory now permits role-group read-only Flask access (750directory/640SQLite/WAL/SHM), with rawPCAP600 and models600/unshared. Web receives no capture or model mount.

Successful operational matrix must have generator errors0, capturecomplete, known drop counts0, scored model outputs and durable PG/Mongo counts after Outbox drain. Interrupted/failed attempts remain diagnostic; new run IDs/versioned series used, never overwritten as success. Performance and fault testing remain separate.

The completed actual fault matrix, mutation and final regression reports are linked in STAGE15_RESULTS when finalized. Synthetic malformed-packet fixtures validate program behavior only, never IDS quality.

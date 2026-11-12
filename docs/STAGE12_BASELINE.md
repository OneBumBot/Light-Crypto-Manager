# Stage12 baseline

Input branch `feature/kuznyechik-mgm-integration`, exact HEAD20d298cc3b48f14920a00e9403bdaf0ff7e38c5a, clean tree. New branch `feature/crypto-comparative-research`. Main unchanged; no push/merge/rebase. Latest migration0010_mgm_key_usage; no schema change needed for implementation optimization.

Stage10/11 reports reviewed: prior50-agent engineering experiment is not repeated/capacity re-proven here. Stage11 scientific comparison is implementation-specific;35 real transitions/11312 admissions are historical data, not Stage12 counts. Policy DRY_RUN, control MANUAL_AUTHORIZED_CONTROL, ML untrusted stay invariant.

New project `lcm-stage12-crypto-research-lab` prepared with fresh CA/TLS/MQTT/HMAC/AEAD credentials, private host inputs and independent named PG/Mongo/device/broker auxiliary volumes. Baseline used original one-shot runtime before provider edits: **868 passed,0 skipped,37.33s, exit0**. Raw baseline-regression.txt retained. Go original executable built twice offline with same pinned source/toolchain: hashes in repro-build-a/b.json. Old Stage11 binary/provider/vendor unchanged as baseline artifacts; no old volumes used.

Current Go upstream pin remained3791d459 on recheck, not assumed unchanged. Candidate revisions and research hashes retained. Runtime dependency is BSD2; GPL Python implementation remains an external offline research checkout, never copied into runtime images.

# Side-channel review — lab restriction retained

Static scope: pinned tarantool3791d459, `kuznyechik/ctkuznyechik.go`, `mgm/mgm.go`, Python bridge and bounded worker. Old vendor source preserved byte-for-byte. No assertion of whole-provider constant-time.

- `NewCipherCT` uses full S-box scan and masked linear columns for Encrypt/Decrypt/key schedule; upstream labels experimental. Compiler/architecture behavior not independently proven.
- MGM `gfMul`: conditional reduction on accumulator overflow depends on key-derived multiplication state; loop branches on multiplier bits, and carry increments exit early on encrypted counters. This is a concrete source-level data-dependence, **not a demonstrated remote exploit**.
- MGM tag uses `subtle.ConstantTimeCompare` before decrypt; invalid tag returns no plaintext. New worker does not replace this with ordinary equality.
- Python PyGOST uses secret-indexed transforms and variable-length integer multiplication loops. Strict validation does not fix timing leakage.
- Packet lengths/status and processing time vary with public lengths and verification outcome; this is not hidden. Different valid/tag-failed operation timing does not itself prove key extraction.
- Key bytes pass private pipes, not argv/env/log. Persistent process increases possible residency; no cache, fresh instances, bounded lifetime and best-effort buffer clear reduce exposure but do not guarantee GC zeroization or protect compromised host.

Offline native timing instrumentation alternates fixed-key and random-key classes,5 independent process runs,5000 samples/class/run, generation and key schedule outside the timed Seal. Welch statistic is descriptive evidence on this x86 host; absence of significance is not proof, significance is not proof of exploitable key leakage. Host scheduling/frequency/cache/GC and class design limit inference. Raw timings retained.

A masked GF rewrite could remove two visible branches but would change authenticated cryptographic arithmetic and still leave counter/compiler/whole-provider questions. This stage does not claim such a patch independently verified; optimization targets IPC only, preserving known-vector/cross-check-tested math. Keep lab-only release; independent audit and platform-specific tooling remain required before production/ARM claims.

Machine-code check: `GOCACHE=<private cache> go tool objdump -s 'github.com/tarantool/go-gostcrypto/mgm.*gfMul' <optimized binary>`, exit0. `gfmul-assembly.txt` shows x86 `JE` at mgm.go:301 after testing the secret-derived overflow bit (address0x491b77 in the recorded binary). This confirms an actual compiled conditional branch for this compiler/architecture, not just a source-level suspicion. No remote key-recovery exploit is claimed; bounds from ideal-cipher analysis do not cover that leakage.

The unique nonce changes on every timing invocation to avoid unsafe benchmark reuse. Consequently, even the fixed-key class varies its key-derived MGM intermediates and may average out leakage. This screening has limited power for that mechanism; it is not a dudect/taint-verification result and no absolute-t threshold is used as a security release pass.

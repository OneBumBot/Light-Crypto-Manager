# Algorithm versus implementation

No strength ranking is inferred from performance. Current supported profiles remain Ascon-AEAD128(key128/tag128,Ascon uses320-bit permutation state and profile-specific nonce16B), AES128-GCM(key128,block128,nonce12B/tag128) and Kuznyechik-MGM(key256,block128,ICN127/tag128). Ascon parameters follow the preserved reference, not an invented block-size equivalence. Magma(block64/key256/ICN63/tag64) remains a research candidate with a negative continuous-telemetry gate.

Ascon reference is pure Python; AES uses optimized cryptography/OpenSSL; Kuznyechik one-shot/worker use the same pinned Go CT cipher/MGM, no new wire profile; strict PyGOST5.12 is an external GPL research backend. All KAT/cross-check claims are scoped to the exact revisions and software environment. No certification, ARM measurement or whole-provider constant-time claim.

Five independent processes/keys for each of5 implementations ×4 payload sizes ×2 AAD modes =200 runs,1000 measured pairs/run after20 warmup. Full raw timings retained. Order rotates; one CPU affinity, services stopped. Point statistics p95/p99 are descriptive within-run percentiles; no packet-as-independent-run confidence interval. No curves interpolate missing payloads.

For83B/fixed128B AAD, median of five run medians, microseconds:

| Implementation | Encrypt | Authenticated decrypt |
|---|---:|---:|
| AES / cryptography native | 1.333 | 1.352 |
| Ascon / Python reference | 271.415 | 272.182 |
| Original immutable Stage11 Go executable / one-shot | 2569.677 | 2566.586 |
| Bounded Go worker | 177.316 | 176.389 |
| PyGOST5.12 / strict research wrapper | 2395.133 | 2394.622 |

A separate rotated-order control using the **same updated dual-mode executable** gives one-shot1620.972us versus worker177.316us encryption, approximately9.14×. Original Stage11 executable SHA256 is5e715633b674a09235ab1bfcbe99f0f283835fb20a7789b869f3e590eb68527a; optimized executable SHA256 is215ede6bfca73ef851bc37a565b864d40901b357c673f153ea0105ad932dedc3. The immutable-original batch was collected later; all datasets use affinity CPU0, but frequency/scheduler/background activity were not isolated. The cause of its difference from the updated one-shot batch was **not established**. Do not attribute that difference solely to source changes, subtract it as crypto time, or advertise the cross-batch ratio as a controlled speedup. Decrypt verifies the tag; bad tags are not treated as successful fast decrypts.

Direct Go83B/AAD128 measurements with reused sequential context: native encrypt median137.722us, decrypt136.900us; warm CT key setup17.733us. Separate actual process startup+empty-input-rejection481.088us(original)/463.039us(optimized); noncrypto echo IPC2.825us. Do not subtract these unrelated medians to manufacture precise algorithm time. First CT-column initialization is not separately isolated; one-shot full path includes it.

CPU series is separate:25 fresh-process runs at83B/fixed AAD, worker warmup process reaped before baseline counters; measured cold/recycle startup retained. Original200-run CPU accounting includes initial worker warmup lifetime and is not used for strict CPU comparison. CPU graph uses measured CPU time per authenticated pair, not misleading saturated-loop utilization as efficiency. Python RSS and child RSS peaks are separate and never summed into a fabricated combined peak.

Native fixed/random classes:5 independent processes,5000 samples/class; descriptive Welch t values −1.418,−1.996,0.752,−0.815,−1.276. These observations do not prove constant-time or absence of exploitable leakage; source-level secret dependence remains.

Magma budget is much shorter than the current lease. Positive public-vector results are algorithm checks, not permission for continuous traffic. Rotation cost is not_measured because a safe rekey lifecycle is not implemented; no zero-cost bar is invented. Magma is absent from MQTT/effective graphs.

The first full matrix used the prerelease worker. After the stderr-EOF availability fix,80 Go one-shot/worker runs and10 CPU runs were repeated with services stopped and rotated pair order. The original immutable executable was subsequently measured in40 runs plus5 CPU runs. `comparative-final.json` contains200 selected runs:120 unchanged Ascon/AES/Python rows,40 refreshed worker rows and40 immutable-original rows; every row identifies its source dataset. `cpu-final.json` similarly contains25 selected runs. These are derived selections, not additional experiments. The paired same-binary control remains in provider-refresh.json. Different experiment times remain a limitation; no CI or hardware-frequency isolation claim.

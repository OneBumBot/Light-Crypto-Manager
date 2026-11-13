# Stage13 verification map

The final results reference the actual JSON/log artifacts; absence of a file is not a PASS. Network cases use new Stage13 credentials/keys/volumes only.

| Property | Behavioral check | Evidence |
|---|---|---|
| Baseline preserved | Full original real PG/Mongo pytest | baseline-regression.txt |
| Late insertion is visible | T+10 then committed T+5; expected late marker | test_policy_throughput / golden-release.json |
| Same-device order and ties |100 events;2/4 serialized workers; reverse-order mutant | golden-release.json, mutations-final.json |
| Mixed source fairness | Full110-source trace, status updates, odd batch/restart | golden-release.json |
| Version/config isolation | Concurrent activation, changed rules, version-bound replay | golden-release.json, policy-reliability.json |
| Atomic source/FSM/dequeue | Rollback hook and actual SIGKILL after claim/before commit | policy-reliability.json |
| Retention | Consumed-only prune, unread guard, identity tombstones, race | unit tests; policy-reliability.json |
| Source conservation | Independent journal↔signals join, per-version unique keys | */ledger-final.json |
| MQTT durability | Formed IDs↔PG↔Mongo, PUBACK separately | performance-summary.json |
| Sustainable processing | Source active throughout300/900s, not only drain | */samples.json, performance-summary.json |
| Overflow visible | Capacity2 overflow1 negative test, real run overflow0 | mutations-final.json, run ledgers |
| ML trust | Research fixtures remain monitor/untrusted; unknown contracts reject | full-regression-final.txt |
| No automatic crypto control | Actual live-control ledger stays empty in Policy experiments | policy-reliability.json, run ledgers |
| Readiness vs freshness | Real stopped/slow Policy worker and DOM assertions | policy-reliability.json/png |
| PG/broker/Mongo recovery | Reused real Stage9 crypto browser fault journey | crypto-browser.json |
| Ascon/AES/Kuz and effective receipts | Real HTTP+CSRF/HMAC/TLS/Device Agent | crypto-browser.json, control-browser.json |
| Malformed MGM recovery | Wrong tag/AAD/types plus subsequent valid packet | poison.json |
| Lost ACK and UNKNOWN_OUTCOME | Actual dropped ACTIVATE ACK, manual reconciliation | lost-ack.json |
| RBAC/CSRF/ACL/XSS | Viewer/operator denial, same-origin DOM/API negatives | crypto-browser.json, control-negatives.txt |
| Source/context preservation | Historical hashes, private inputs, images/roles/keys scan | preservation-after.json |

All cryptographic KAT/provider/nonce/replay, Policy/ML contracts, Socket.IO and Ground Truth regression tests remain. Hardware ARM, trusted live IDS, new RF/IF training, Magma live and production Kuz promotion are outside this stage.

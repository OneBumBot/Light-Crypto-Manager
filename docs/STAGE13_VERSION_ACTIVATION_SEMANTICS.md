# Stage13 version activation

The existing immutable version/config SHA and install transaction advisory lock remain authority. Batches acquire that same exclusive transaction lock before loading the active version. One bounded transaction uses one immutable Rules object tied to that exact version. A pending administrator activation waits for batch commit/rollback. The next batch reloads active version; no persistent in-memory version/rules cache.

Activating a version inserts all **retained** security observations and current non-processing ML status identities missing from policy_signals(event_id,version) into the global pending queue, ON CONFLICT DO NOTHING. Existing unprocessed snapshots remain pending. Inserts concurrent with activation always enqueue independently of version selection. Therefore no timestamp boundary or insertion/activation race loses an event.

Historical retained sources may be replayed under a newly activated version, as with the original version-scoped NOT EXISTS implementation. Age/late diagnostics use that version's rules and actual evaluation time; old history is not synthetic fresh evidence. Existing process() carries guard/last decision/cooldown from prior state, resets only the established recovery accumulation at version boundaries and preserves command counters. Reactivation obeys existing per-version identity tombstones; no old decisions are overwritten.

Retention removes only consumed source rows under the active version and retains signal identity tombstones. Already explicitly pruned source payloads are not recreated by activation; this was never an infinite source-replay archive. Pending rows are protected from deletion. No telemetry replay, control command, effective receipt, model registry or MGM usage authority is modified.

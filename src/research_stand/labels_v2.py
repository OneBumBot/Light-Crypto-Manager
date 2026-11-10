"""Versioned connection/window annotations. No packet attack ground truth under TLS."""

import statistics

VERSION = "connection-evidence-v2.1"
REASONS = {
    "normal": "broker_session_and_receiver_event",
    "bad_credentials": "broker_connack_denied_session",
    "forbidden_acl": "broker_acl_denied_session",
    "replay": "broker_nondup_repeat_and_timed_authenticated_replay",
    "bounded_rate": "broker_observed_publish_rate_window",
    "pattern_change": "broker_observed_publish_interval_window",
}


def session(record, broker):
    if broker.get("schema_version") != 2 or broker.get("source") != "docker_mosquitto_log":
        return None
    found = [
        s
        for s in broker["sessions"]
        if s["client_id"] == record["client_id"]
        and s["ip"] == record["local_ip"]
        and s["port"] == record["local_port"]
        and record["attempt_started_at"] - 0.02 <= s["opened_at"] <= record["tls_open_at"] + 0.02
        and s["authenticated_at"] <= record["closed_at"] + 0.02
    ]
    return found[0] if len(found) == 1 else None


def verdict(record, truth, broker, core):
    s = session(record, broker)
    activity = record["activity"]
    lo = record["tls_open_at"]
    hi = record["closed_at"]
    if s is None:
        return "unknown", "independent_session_evidence_missing", "", lo, hi
    if activity == "bad_credentials":
        return (
            ("controlled_violation", REASONS[activity], "", lo, hi)
            if s["auth_code"] == 5 and record.get("auth_rejected")
            else ("unknown", "contradictory_or_unconfirmed_auth_result", "", lo, hi)
        )
    device = record["logical_device"]
    if s["auth_code"] != 0 or s["username"] != "device_" + device:
        return "unknown", "authenticated_identity_mismatch", "", lo, hi
    device_binding = device
    events = [e for e in s["events"] if lo - 0.02 <= e["at"] <= hi + 0.02]
    pubs = [e for e in events if e["kind"] == "publish" and e["topic"] == "iot/sensors/" + device]
    pg = [
        e
        for e in core.get("security_events", [])
        if e["device_id"] == device and lo - 0.02 <= e["occurred_at"] <= hi + 0.1
    ]
    if activity == "normal":
        healthy = any(e["category"] == "accepted" for e in pg)
        retry = any(e.get("dup") == 1 for e in pubs) and any(e["category"] == "replay" for e in pg)
        good = (
            bool(pubs) and (healthy or retry) and not any(e["kind"] == "acl_denied" for e in events)
        )
    elif activity == "forbidden_acl":
        good = any(e["kind"] == "acl_denied" for e in events)
    elif activity == "replay":
        identities = {(a["key_epoch"], a["sequence_number"]) for a in record["actions"]}
        prior = [
            e
            for e in core.get("security_events", [])
            if e["device_id"] == device
            and e["category"] == "accepted"
            and e["occurred_at"] < lo
            and (e["key_epoch"], e["sequence_number"]) in identities
        ]
        repeated = [
            e
            for e in pg
            if e["category"] == "replay" and (e["key_epoch"], e["sequence_number"]) in identities
        ]
        prep = [
            r
            for r in truth["connections"]
            if r["activity"] == "normal"
            and r["logical_device"] == device
            and r.get("closed_at", float("inf")) < lo
            and any(
                (a["key_epoch"], a["sequence_number"], a["payload_sha256"])
                == (b["key_epoch"], b["sequence_number"], b["payload_sha256"])
                for a in r["actions"]
                for b in record["actions"]
            )
        ]
        witness = core.get("mqtt_witness", {})
        witnessed = [
            e
            for e in witness.get("events", [])
            if e.get("candidate_identity")
            and tuple(e["candidate_identity"]) in {(device, a, b) for a, b in identities}
        ]
        originals = [e for e in witnessed if e["at"] < lo]
        repeats = [e for e in witnessed if lo <= e["at"] <= hi + 0.1]
        expected_hashes = {a["payload_sha256"] for a in record["actions"]}
        digest_proof = (
            witness.get("source") == "independent_read_only_mqtt_fanout"
            and not witness.get("overflow", True)
            and bool(originals and repeats)
            and {e["payload_sha256"] for e in witnessed} == expected_hashes
        )
        good = (
            bool(prior and repeated and prep and pubs)
            and all(e["dup"] == 0 for e in pubs)
            and digest_proof
        )
    elif activity in {"bounded_rate", "pattern_change"}:
        unique = {e["mid"]: e for e in pubs if e["dup"] == 0}
        points = sorted(e["at"] for e in unique.values())
        deltas = [b - a for a, b in zip(points, points[1:])]
        nominal = truth["experiment"]["interval"]
        jitter = truth["experiment"]["jitter"]
        good = False
        peers = []
        for other in truth["connections"]:
            if other["activity"] != "normal" or other["connection_id"] == record["connection_id"]:
                continue
            ps = session(other, broker)
            if ps and ps["auth_code"] == 0:
                pt = sorted(
                    {
                        e["mid"]: e["at"]
                        for e in ps["events"]
                        if e["kind"] == "publish" and e["dup"] == 0
                    }.values()
                )
                if len(pt) >= 6:
                    peers.append(statistics.median(b - a for a, b in zip(pt, pt[1:])))
        baseline = any(abs(x - nominal) <= jitter + 0.05 for x in peers)
        if len(points) >= 8 and baseline:
            if activity == "bounded_rate":
                good = (
                    statistics.median(deltas) <= 0.75 * nominal
                    and sum(abs(x - 0.5 * nominal) <= jitter + 0.05 for x in deltas) / len(deltas)
                    >= 0.9
                )
            else:
                low = sum(x < 0.8 * nominal for x in deltas)
                high = sum(x > 1.2 * nominal for x in deltas)
                alternating = sum(
                    (a < 0.8 * nominal and b > 1.2 * nominal)
                    or (b < 0.8 * nominal and a > 1.2 * nominal)
                    for a, b in zip(deltas, deltas[1:])
                )
                good = low >= 3 and high >= 3 and alternating / max(1, len(deltas) - 1) >= 0.7
            lo = max(lo, points[0] + 0.02)
            hi = min(hi, points[-1] - 0.02)
    else:
        return "unknown", "anonymous_or_uncorrelated_server_outcome", device_binding, lo, hi
    return (
        (
            "controlled_violation" if activity != "normal" else "normal",
            REASONS[activity],
            device_binding,
            lo,
            hi,
        )
        if good
        else ("unknown", "scenario_unverified", device_binding, lo, hi)
    )


def annotate(rows, truth, broker, core):
    grouped = {}
    for row in rows:
        grouped.setdefault(row["tcp.stream"], []).append(row)
    assigned = {}
    for key, group in grouped.items():
        wire = (
            group[0]["ip.src"],
            group[0]["tcp.srcport"],
            group[0]["ip.dst"],
            group[0]["tcp.dstport"],
        )
        reverse = (wire[2], wire[3], wire[0], wire[1])
        matches = [
            r
            for r in truth["connections"]
            if (
                r.get("local_ip"),
                str(r.get("local_port")),
                r.get("remote_ip"),
                str(r.get("remote_port")),
            )
            in (wire, reverse)
        ]
        syn = any(int(r["tcp.flags"], 0) & 2 and not int(r["tcp.flags"], 0) & 16 for r in group)
        if syn and len(matches) == 1:
            assigned[key] = matches[0]
    output = []
    for row in rows:
        record = assigned.get(row["tcp.stream"])
        label = "unknown"
        reason = "unmapped_connection_or_boundary"
        device = ""
        kind = "unattributed"
        connection = ""
        scope = "connection_activity"
        if record:
            connection = record["connection_id"]
            kind = record["activity"]
            scope = (
                "window_behavior"
                if kind in {"bounded_rate", "pattern_change"}
                else "connection_activity"
            )
            state, why, binding, lo, hi = verdict(record, truth, broker, core)
            t = float(row["frame.time_epoch"])
            margin = max(0.00005, truth["clock"]["boundary_margin_seconds"])
            if lo + margin <= t <= hi - margin:
                label, reason, device = state, why, binding
        output.append(
            dict(
                **row,
                ground_truth=label,
                label_reason=reason,
                connection_id=connection,
                authenticated_device=device,
                direction=(
                    "client_to_broker"
                    if row["ip.src"] == record["local_ip"]
                    and row["tcp.srcport"] == str(record["local_port"])
                    else "broker_to_client"
                )
                if record
                else "unknown",
                label_confidence="corroborated_activity" if label != "unknown" else "unconfirmed",
                label_unit="connection_activity",
                label_scope=scope,
                connection_activity=kind,
                packet_specific_evidence="none_encrypted_tls",
                label_evidence_level="independent_source_activity"
                if label != "unknown"
                else "insufficient",
            )
        )
    return output

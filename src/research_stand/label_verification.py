"""Independent reconciliation oracle: raw PCAP -> identity invariants -> saved rows.
Never imports builder, annotate(), verdict(), or old map_packets(). Shared I/O only.
It validates connection/window annotations, not maliciousness of TLS packets.
"""

import argparse, csv, json, math, statistics
from collections import Counter, defaultdict
from itertools import islice
from pathlib import Path
from .pcap_audit import headers, load_json, digest

FIELDS = ["frame.len", "tcp.len", "tcp.flags", "tcp.window_size_value", "tcp.time_delta"]


def expected(row, all_rows, truth, broker, core):
    """Separate invariant-oriented oracle; intentionally not a call to the labeler."""
    wire = (row["ip.src"], row["tcp.srcport"], row["ip.dst"], row["tcp.dstport"])
    reverse = (wire[2], wire[3], wire[0], wire[1])
    candidates = []
    for r in truth["connections"]:
        if (
            r.get("local_ip"),
            str(r.get("local_port")),
            r.get("remote_ip"),
            str(r.get("remote_port")),
        ) in (wire, reverse):
            candidates.append(r)
    syn = False
    for p in all_rows:
        if p["tcp.stream"] == row["tcp.stream"]:
            flags = int(p["tcp.flags"], 0)
            if flags & 2 and not flags & 16:
                syn = True
    r = candidates[0] if len(candidates) == 1 and syn else None
    out = dict(
        ground_truth="unknown",
        label_reason="unmapped_connection_or_boundary",
        connection_id="",
        authenticated_device="",
        direction="unknown",
        label_confidence="unconfirmed",
        label_unit="connection_activity",
        label_scope="connection_activity",
        connection_activity="unattributed",
        packet_specific_evidence="none_encrypted_tls",
        label_evidence_level="insufficient",
    )
    if not r:
        return out
    kind = r["activity"]
    lo = r["tls_open_at"]
    hi = r["closed_at"]
    binding = ""
    label = "unknown"
    why = "independent_session_evidence_missing"
    out.update(
        connection_id=r["connection_id"],
        connection_activity=kind,
        label_scope="window_behavior"
        if kind in ("bounded_rate", "pattern_change")
        else "connection_activity",
        direction="client_to_broker"
        if wire[:2] == (r["local_ip"], str(r["local_port"]))
        else "broker_to_client",
    )
    server = []
    if broker.get("schema_version") == 2 and broker.get("source") == "docker_mosquitto_log":
        for s in broker["sessions"]:
            if (
                (s["client_id"], s["ip"], s["port"])
                == (r["client_id"], r["local_ip"], r["local_port"])
                and r["attempt_started_at"] - 0.02 <= s["opened_at"] <= lo + 0.02
                and s["authenticated_at"] <= hi + 0.02
            ):
                server.append(s)
    if len(server) == 1:
        s = server[0]
        if kind == "bad_credentials":
            why = "contradictory_or_unconfirmed_auth_result"
            if s["auth_code"] == 5 and r.get("auth_rejected"):
                label = "controlled_violation"
                why = "broker_connack_denied_session"
        elif s["auth_code"] != 0 or s["username"] != "device_" + r["logical_device"]:
            why = "authenticated_identity_mismatch"
        else:
            binding = r["logical_device"]
            ev = [e for e in s["events"] if lo - 0.02 <= e["at"] <= hi + 0.02]
            pubs = [
                e for e in ev if e["kind"] == "publish" and e["topic"] == "iot/sensors/" + binding
            ]
            points = [
                e
                for e in core.get("security_events", [])
                if e["device_id"] == binding and lo - 0.02 <= e["occurred_at"] <= hi + 0.1
            ]
            why = "scenario_unverified"
            good = False
            if kind == "normal":
                good = (
                    bool(pubs)
                    and (
                        any(e["category"] == "accepted" for e in points)
                        or (
                            any(e["dup"] == 1 for e in pubs)
                            and any(e["category"] == "replay" for e in points)
                        )
                    )
                    and not any(e["kind"] == "acl_denied" for e in ev)
                )
                if good:
                    label = "normal"
                    why = "broker_session_and_receiver_event"
            elif kind == "forbidden_acl":
                if any(e["kind"] == "acl_denied" for e in ev):
                    label = "controlled_violation"
                    why = "broker_acl_denied_session"
            elif kind == "replay":
                actions = {
                    (a["key_epoch"], a["sequence_number"], a["payload_sha256"])
                    for a in r["actions"]
                }
                identity = {(e, s) for e, s, _ in actions}
                accepted = [
                    e
                    for e in core.get("security_events", [])
                    if e["device_id"] == binding
                    and e["category"] == "accepted"
                    and e["occurred_at"] < lo
                    and (e["key_epoch"], e["sequence_number"]) in identity
                ]
                prior = []
                for old in truth["connections"]:
                    if (
                        old["logical_device"] == binding
                        and old["activity"] == "normal"
                        and old.get("closed_at", float("inf")) < lo
                    ):
                        prior.extend(
                            a
                            for a in old["actions"]
                            if (a["key_epoch"], a["sequence_number"], a["payload_sha256"])
                            in actions
                        )
                good = (
                    bool(prior and accepted and pubs)
                    and all(e["dup"] == 0 for e in pubs)
                    and any(
                        e["category"] == "replay"
                        and (e["key_epoch"], e["sequence_number"]) in identity
                        for e in points
                    )
                )
                witness = core.get("mqtt_witness", {})
                witness_rows = [
                    e
                    for e in witness.get("events", [])
                    if e.get("candidate_identity")
                    and e["candidate_identity"][0] == binding
                    and tuple(e["candidate_identity"][1:]) in identity
                ]
                witness_ok = (
                    witness.get("source") == "independent_read_only_mqtt_fanout"
                    and witness.get("overflow") is False
                    and any(e["at"] < lo for e in witness_rows)
                    and any(lo <= e["at"] <= hi + 0.1 for e in witness_rows)
                )
                witness_ok = witness_ok and set(e["payload_sha256"] for e in witness_rows) == {
                    h for _, _, h in actions
                }
                if good and witness_ok:
                    label = "controlled_violation"
                    why = "broker_nondup_repeat_and_timed_authenticated_replay"
            elif kind in ("bounded_rate", "pattern_change"):
                ts = sorted({e["mid"]: e["at"] for e in pubs if not e["dup"]}.values())
                gaps = [ts[i] - ts[i - 1] for i in range(1, len(ts))]
                reference = False
                nominal = truth["experiment"]["interval"]
                jitter = truth["experiment"]["jitter"]
                for peer in truth["connections"]:
                    if peer["activity"] != "normal" or peer["connection_id"] == r["connection_id"]:
                        continue
                    peer_sessions = [
                        p
                        for p in broker["sessions"]
                        if p["client_id"] == peer["client_id"]
                        and p["ip"] == peer["local_ip"]
                        and p["port"] == peer["local_port"]
                        and peer["attempt_started_at"] - 0.02
                        <= p["opened_at"]
                        <= peer["tls_open_at"] + 0.02
                        and p["authenticated_at"] <= peer["closed_at"] + 0.02
                    ]
                    if len(peer_sessions) == 1 and peer_sessions[0]["auth_code"] == 0:
                        pt = sorted(
                            {
                                p["mid"]: p["at"]
                                for p in peer_sessions[0]["events"]
                                if p["kind"] == "publish" and p["dup"] == 0
                            }.values()
                        )
                        if (
                            len(pt) >= 6
                            and abs(
                                statistics.median(pt[i] - pt[i - 1] for i in range(1, len(pt)))
                                - nominal
                            )
                            <= jitter + 0.05
                        ):
                            reference = True
                if len(ts) >= 8 and reference:
                    if kind == "bounded_rate":
                        good = statistics.median(gaps) <= nominal * 0.75 and len(
                            [x for x in gaps if abs(x - nominal * 0.5) <= jitter + 0.05]
                        ) >= 0.9 * len(gaps)
                    else:
                        flags = [
                            -1 if x < nominal * 0.8 else 1 if x > nominal * 1.2 else 0 for x in gaps
                        ]
                        good = (
                            flags.count(-1) >= 3
                            and flags.count(1) >= 3
                            and sum(a * b == -1 for a, b in zip(flags, flags[1:]))
                            >= 0.7 * max(1, len(flags) - 1)
                        )
                    lo = max(lo, ts[0] + 0.02)
                    hi = min(hi, ts[-1] - 0.02)
                if good:
                    label = "controlled_violation"
                    why = (
                        "broker_observed_publish_rate_window"
                        if kind == "bounded_rate"
                        else "broker_observed_publish_interval_window"
                    )
            else:
                why = "anonymous_or_uncorrelated_server_outcome"
    t = float(row["frame.time_epoch"])
    margin = max(0.00005, truth["clock"]["boundary_margin_seconds"])
    if lo + margin <= t <= hi - margin:
        out.update(
            ground_truth=label,
            label_reason=why,
            authenticated_device=binding,
            label_confidence="corroborated_activity" if label != "unknown" else "unconfirmed",
            label_evidence_level="independent_source_activity"
            if label != "unknown"
            else "insufficient",
        )
    return out


def table(path):
    if Path(path).stat().st_size > 128 * 1024**2:
        raise ValueError("Derived table resource bound")
    with Path(path).open() as f:
        rows = list(islice(csv.DictReader(f), 100001))
    if len(rows) > 100000:
        raise ValueError("Derived row bound")
    return rows


def reconcile(directory, captures):
    directory = Path(directory)
    captures = Path(captures)
    m = load_json(directory / "dataset.manifest.json")
    if m.get("label_rules_version") != "connection-evidence-v2.1":
        raise ValueError("Use legacy reconciliation for archival v1")
    if (
        digest(directory / "dataset.csv") != m["sha256"]
        or digest(directory / "observations.csv") != m["observations_sha256"]
    ):
        raise ValueError("Derived hash mismatch")
    if m.get("feature_order") != FIELDS or m.get("granularity") != "packet":
        raise ValueError("Feature identity/schema mismatch")
    if m.get("data_quality", {}).get("scientific_quality_available") is True:
        raise ValueError("Unsubstantiated scientific quality attestation")
    obs = table(directory / "observations.csv")
    known = table(directory / "dataset.csv")
    by_capture = defaultdict(list)
    for row in obs:
        by_capture[row["experiment_id"]].append(row)
    if len({r["packet_id"] for r in obs}) != len(obs):
        raise ValueError("Duplicate physical packet identity")
    if set(by_capture) != {r["capture_id"] for r in m["raw_files"]}:
        raise ValueError("Capture set mismatch")
    counts = Counter()
    connections = set()
    verified = set()
    for capture in m["raw_files"]:
        folder = captures / capture["capture_id"]
        if folder.resolve().parent != captures.resolve():
            raise ValueError("Unsafe capture identity")
        for name, value in capture["input_hashes"].items():
            if Path(name).name != name or digest(folder / name) != value:
                raise ValueError("Source evidence hash mismatch")
        raw, cap, _ = headers(folder)
        truth = load_json(folder / "ground-truth.json")
        core = load_json(folder / "core.json")
        core["mqtt_witness"] = (
            load_json(folder / "mqtt-observer.json")
            if (folder / "mqtt-observer.json").exists()
            else {}
        )
        broker = (
            load_json(folder / "broker-evidence.json")
            if (folder / "broker-evidence.json").exists()
            else {}
        )
        raw_by_stream = defaultdict(list)
        for p in raw:
            raw_by_stream[p["tcp.stream"]].append(p)
        saved = by_capture[capture["capture_id"]]
        if len(saved) != len(raw):
            raise ValueError("Missing/extra observation")
        prefix = "lightcrypto-lab-fixed:" + folder.name
        for original, actual in zip(raw, saved):
            required = expected(
                original, raw_by_stream[original["tcp.stream"]], truth, broker, core
            )
            required.update(
                source_id="lightcrypto-lab-fixed",
                capture_id=prefix,
                experiment_id=folder.name,
                session_id=prefix + ":" + original["tcp.stream"],
                packet_id=prefix + ":" + original["frame.number"],
                feature_version="tcp-packet-passive-v1",
                source_pcap_sha256=cap["pcap_sha256"],
                scenario_category=truth["experiment"]["scenario"],
                label_source="connection-evidence-v2.1",
            )
            required.update(
                label={"normal": "0", "controlled_violation": "1", "unknown": ""}[
                    required["ground_truth"]
                ],
                attack_type={
                    "normal": "Normal",
                    "controlled_violation": "ControlledViolation",
                    "unknown": "Unknown",
                }[required["ground_truth"]],
            )
            for field, value in required.items():
                if actual.get(field) != str(value):
                    raise ValueError("Logical reconciliation mismatch: " + field)
            if abs(float(actual["epoch_seconds"]) - float(original["frame.time_epoch"])) > 1e-7:
                raise ValueError("Saved timestamp mismatch")
            for f in FIELDS:
                v = int(original[f], 0) if f == "tcp.flags" else float(original[f])
                if float(actual[f]) != v:
                    raise ValueError("Saved feature mismatch: " + f)
            counts[actual["ground_truth"]] += 1
            connections.add(actual["connection_id"])
            if actual["ground_truth"] != "unknown":
                verified.add(actual["connection_id"])
    expected_known = [r for r in obs if r["ground_truth"] != "unknown"]
    if known != expected_known:
        raise ValueError("Unknown promotion or missing/extra/mutated training row")
    if (
        m.get("rows") != len(known)
        or m.get("observations") != len(obs)
        or m.get("unknown_excluded") != counts["unknown"]
    ):
        raise ValueError("Manifest observation counts mismatch")
    if m.get("provenance", {}).get("independent_label_verification") and not verified:
        raise ValueError("No independently corroborated labels")
    return dict(
        schema_version=2,
        reconciliation="matched",
        physical_packets=len(obs),
        class_counts=dict(counts),
        corroborated_connections=len(verified),
        independent_algorithm=True,
        malicious_packet_accuracy=None,
        real_attack_detection_unproven=True,
        files_modified=False,
    )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", required=True)
    p.add_argument("--captures", required=True)
    p.add_argument("--output")
    a = p.parse_args()
    result = reconcile(a.dataset, a.captures)
    if a.output:
        with Path(a.output).open("x") as f:
            json.dump(result, f, indent=2)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()


def legacy_reconcile(directory, captures):
    """Reconstruct historical weak rules independently; NEVER attest scientific labels."""
    directory = Path(directory)
    captures = Path(captures)
    m = load_json(directory / "dataset.manifest.json")
    obs = table(directory / "observations.csv")
    known = table(directory / "dataset.csv")
    by = defaultdict(list)
    for r in obs:
        by[r["experiment_id"]].append(r)
    if set(by) != {r["capture_id"] for r in m["raw_files"]} or len(
        {r["packet_id"] for r in obs}
    ) != len(obs):
        raise ValueError("Historical packet/capture set mismatch")
    total = 0
    for source in m["raw_files"]:
        folder = captures / source["capture_id"]
        raw, cap, _ = headers(folder)
        truth = load_json(folder / "ground-truth.json")
        core = load_json(folder / "core.json")
        broker = load_json(folder / "broker-events.json")
        saved = by[source["capture_id"]]
        if len(saved) != len(raw):
            raise ValueError("Historical missing/extra packet")
        for packet, row in zip(raw, saved):
            wire = (
                packet["ip.src"],
                packet["tcp.srcport"],
                packet["ip.dst"],
                packet["tcp.dstport"],
            )
            reverse = (wire[2], wire[3], wire[0], wire[1])
            matches = [
                c
                for c in truth["connections"]
                if (
                    c.get("local_ip"),
                    str(c.get("local_port")),
                    c.get("remote_ip"),
                    str(c.get("remote_port")),
                )
                in (wire, reverse)
            ]
            syn = any(
                p["tcp.stream"] == packet["tcp.stream"]
                and int(p["tcp.flags"], 0) & 2
                and not int(p["tcp.flags"], 0) & 16
                for p in raw
            )
            r = matches[0] if len(matches) == 1 and syn else None
            label = "unknown"
            reason = "unmapped_connection_or_boundary"
            device = ""
            if (
                r
                and r.get("tls_open_at")
                and r.get("closed_at")
                and r["tls_open_at"] + truth["clock"]["boundary_margin_seconds"]
                <= float(packet["frame.time_epoch"])
                <= r["closed_at"] - truth["clock"]["boundary_margin_seconds"]
            ):
                kind = r["activity"]
                ok = bool(r["confirmed"])
                if kind == "normal":
                    ok = (
                        ok
                        and r["authenticated"]
                        and r["logical_device"] in core.get("accepted_devices", [])
                    )
                elif kind == "bad_credentials":
                    ok = ok and r["auth_rejected"]
                elif kind == "forbidden_acl":
                    ok = ok and r.get("client_id") in broker.get("acl_denied_clients", [])
                elif kind == "tampered":
                    ok = (
                        ok
                        and r.get("local_crypto_rejection", False)
                        and core.get("rejected_delta", 0) > 0
                    )
                elif kind == "replay":
                    ok = ok and any(
                        [r["logical_device"], a["key_epoch"], a["sequence_number"]]
                        in core.get("replay_identities", [])
                        for a in r["actions"]
                    )
                elif kind in ["bounded_rate", "pattern_change"]:
                    ok = ok and r["authenticated"] and len(r["actions"]) >= 2
                else:
                    ok = False
                if ok:
                    label = "normal" if kind == "normal" else "controlled_violation"
                    reason = "process_socket_tuple+captured_SYN+TLS_interval+controlled_outcome"
                    device = r["logical_device"] if r["authenticated"] else ""
            prefix = "lightcrypto-lab-75b:" + folder.name
            required = dict(
                ground_truth=label,
                label_reason=reason,
                connection_id=r["connection_id"] if r else "",
                authenticated_device=device,
                direction=(
                    "client_to_broker"
                    if wire[:2] == (r["local_ip"], str(r["local_port"]))
                    else "broker_to_client"
                )
                if r
                else "unknown",
                label_confidence="verified" if label != "unknown" else "ambiguous",
                source_id="lightcrypto-lab-75b",
                capture_id=prefix,
                experiment_id=folder.name,
                packet_id=prefix + ":" + packet["frame.number"],
                session_id=prefix + ":" + packet["tcp.stream"],
                source_pcap_sha256=cap["pcap_sha256"],
                feature_version="tcp-packet-passive-v1",
                label_source="controlled_orchestrator+socket+outcome",
                scenario_category=truth["experiment"]["scenario"],
                attack_type={
                    "normal": "Normal",
                    "controlled_violation": "ControlledViolation",
                    "unknown": "Unknown",
                }[label],
            )
            for field, value in required.items():
                if row.get(field) != value:
                    raise ValueError("Historical logical reconciliation mismatch: " + field)
            if (label == "unknown" and row["label"] != "") or (
                label != "unknown" and float(row["label"]) != int(label == "controlled_violation")
            ):
                raise ValueError("Historical binary label mismatch")
            if abs(float(row["epoch_seconds"]) - float(packet["frame.time_epoch"])) > 1e-7:
                raise ValueError("Historical timestamp mismatch")
            for f in FIELDS:
                if float(row[f]) != (int(packet[f], 0) if f == "tcp.flags" else float(packet[f])):
                    raise ValueError("Historical feature mismatch")
            total += 1

    def canonical(row):
        return {**row, "label": str(int(float(row["label"])))}

    if [canonical(r) for r in known] != [
        canonical(r) for r in obs if r["ground_truth"] != "unknown"
    ]:
        raise ValueError("Historical unknown promotion/training mismatch")
    return dict(
        reconciliation="historical_rule_reproduction_only",
        physical_packets=total,
        independent_label_verification=False,
        legacy_evidence_insufficient=True,
        malicious_packet_accuracy=None,
        files_modified=False,
    )

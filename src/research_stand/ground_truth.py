"""Connection attribution, never a capture-wide attack label. Pure offline mapping."""

import math


def tuple_of(record):
    return (
        record.get("local_ip"),
        str(record.get("local_port")),
        record.get("remote_ip"),
        str(record.get("remote_port")),
    )


def packet_tuple(row):
    return (row["ip.src"], row["tcp.srcport"], row["ip.dst"], row["tcp.dstport"])


def map_packets(rows, truth, broker_events, core):
    margin = truth["clock"]["boundary_margin_seconds"]
    if not math.isfinite(margin) or margin < 0.00005:
        raise ValueError("Invalid clock uncertainty")
    records = truth["connections"]
    ids = [r["connection_id"] for r in records]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate connection identity")
    streams = {}
    for row in rows:
        streams.setdefault(row["tcp.stream"], []).append(row)
    mappings = {}
    for stream, packets in streams.items():
        # Stream must have a SYN captured and a unique tuple, not just a time overlap.
        first = packets[0]
        wire = packet_tuple(first)
        rev = (wire[2], wire[3], wire[0], wire[1])
        has_syn = any(
            int(r["tcp.flags"], 0) & 2 and not int(r["tcp.flags"], 0) & 16 for r in packets
        )
        matches = [r for r in records if tuple_of(r) in (wire, rev)]
        if has_syn and len(matches) == 1 and all(packet_tuple(p) in (wire, rev) for p in packets):
            mappings[stream] = matches[0]
    out = []
    for row in rows:
        r = mappings.get(row["tcp.stream"])
        label = "unknown"
        why = "unmapped_connection_or_boundary"
        device = None
        t = float(row["frame.time_epoch"])
        if (
            r
            and r.get("tls_open_at")
            and r.get("closed_at")
            and r["tls_open_at"] + margin <= t <= r["closed_at"] - margin
        ):
            kind = r["activity"]
            proof = bool(r["confirmed"])
            if kind == "normal":
                proof = (
                    proof
                    and r["authenticated"]
                    and r["logical_device"] in core.get("accepted_devices", [])
                )
            elif kind == "bad_credentials":
                proof = proof and r["auth_rejected"]
            elif kind == "forbidden_acl":
                proof = proof and r.get("client_id") in broker_events.get("acl_denied_clients", [])
            elif kind == "replay":
                proof = proof and any(
                    (r["logical_device"], a["key_epoch"], a["sequence_number"])
                    in {tuple(x) for x in core.get("replay_identities", [])}
                    for a in r["actions"]
                )
            elif kind == "tampered":
                proof = (
                    proof
                    and r.get("local_crypto_rejection", False)
                    and core.get("rejected_delta", 0) > 0
                )
            elif kind in {"bounded_rate", "pattern_change"}:
                proof = proof and r["authenticated"] and len(r["actions"]) >= 2
            else:
                proof = False
            if proof:
                label = "normal" if kind == "normal" else "controlled_violation"
                why = "process_socket_tuple+captured_SYN+TLS_interval+controlled_outcome"
                # A rejected credential is not an authenticated identity.
                device = r["logical_device"] if r["authenticated"] else None
        out.append(
            {
                **row,
                "ground_truth": label,
                "label_reason": why,
                "connection_id": r["connection_id"] if r else "",
                "authenticated_device": device or "",
                "direction": (
                    "client_to_broker" if packet_tuple(row) == tuple_of(r) else "broker_to_client"
                )
                if r
                else "unknown",
                "label_confidence": "verified" if label != "unknown" else "ambiguous",
            }
        )
    return out

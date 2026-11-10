"""Synthetic protocol-shaped PCAP fixtures. Not real TLS/attack measurements.
Positive oracle reconciliation and coherent-hash tampering exercise PUBLIC pipeline.
"""

import copy, csv, json, struct, hashlib
from pathlib import Path
import pandas as pd
import pytest
from src.research_stand.dataset_v2 import build
from src.research_stand.label_verification import reconcile
from src.research_stand.pcap_audit import digest
from src.research_stand.quality import statuses


def fixture(
    root,
    kind="bad_credentials",
    changed=True,
    broker_available=True,
    no_syn=False,
    few=False,
    tcp_variant=None,
):
    folder = root / "capture"
    folder.mkdir(parents=True)
    regular = [2 + i * 0.5 for i in range(10)]
    times = (
        regular
        if not changed or kind not in ["bounded_rate", "pattern_change"]
        else [2 + i * 0.25 for i in range(12)]
        if kind == "bounded_rate"
        else [2, 2.25, 3, 3.25, 4, 4.25, 5, 5.25, 6, 6.25]
    )
    if few:
        times = times[:2]
    points = []
    connections = []
    sessions = []
    events = []
    for index, (activity, ts) in enumerate([("normal", regular), (kind, times)]):
        port = 40000 + index * 1000
        device = "lab00" + str(index + 1)
        client = "lab-" + str(index) * 32
        r = dict(
            connection_id="connection-" + str(index),
            client_id=client,
            local_ip="172.31.0.8",
            local_port=port,
            remote_ip="172.31.0.3",
            remote_port=8883,
            logical_device=device,
            activity=activity,
            attempt_started_at=1 + index * 0.1,
            tls_open_at=1.5,
            closed_at=9.0,
            authenticated=activity != "bad_credentials",
            auth_rejected=activity == "bad_credentials",
            confirmed=True,
            actions=[],
            normal_retry_dup_observed=False,
        )
        s = dict(
            ip=r["local_ip"],
            port=port,
            client_id=client,
            opened_at=r["attempt_started_at"],
            authenticated_at=1.6,
            closed_at=9.0,
            auth_code=5 if activity == "bad_credentials" else 0,
            username=None if activity == "bad_credentials" else "device_" + device,
            events=[],
        )
        points.append((r["attempt_started_at"], index, 16 if no_syn else 2, 0))
        for n, t in enumerate(ts):
            points.append(
                (t, index, 24, 2048 if tcp_variant == "packet_size_only" and index == 1 else 30)
            )
            if tcp_variant == "tcp_retransmissions_only" and index == 1:
                points.extend((t + d, index, 24, 30) for d in [0.001, 0.002, 0.003])
            s["events"].append(
                dict(
                    kind="acl_denied" if activity == "forbidden_acl" else "publish",
                    at=t + 0.001,
                    dup=0,
                    mid=n + 1,
                    topic="iot/sensors/lab000"
                    if activity == "forbidden_acl"
                    else "iot/sensors/" + device,
                )
            )
            r["actions"].append(
                dict(key_epoch=1, sequence_number=n + 1, payload_sha256="a" * 64, sent_at=t)
            )
            if activity == "normal":
                events.append(
                    dict(
                        id=device + str(n),
                        category="accepted",
                        device_id=device,
                        key_epoch=1,
                        sequence_number=n + 1,
                        occurred_at=t + 0.002,
                    )
                )
        points.append((8.8, index, 16, 0))
        connections.append(r)
        sessions.append(s)
    raw = bytearray(struct.pack("<IHHIIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1))
    rows = []
    last = {}
    for number, (t, index, flags, size) in enumerate(sorted(points), 1):
        port = 40000 + index * 1000
        ethernet = b"\x00" * 12 + b"\x08\x00"
        ip = struct.pack(
            "!BBHHHBBH4s4s",
            0x45,
            0,
            40 + size,
            number,
            0,
            64,
            6,
            0,
            bytes([172, 31, 0, 8]),
            bytes([172, 31, 0, 3]),
        )
        tcp = struct.pack(
            "!HHIIBBHHH",
            port,
            8883,
            int(t * 2) * 30
            if tcp_variant == "tcp_retransmissions_only" and index == 1 and size
            else number,
            0,
            0x50,
            flags,
            512,
            0,
            0,
        )
        frame = ethernet + ip + tcp + b"S" * size
        sec = int(t)
        micros = round((t - sec) * 1e6)
        raw += struct.pack("<IIII", sec, micros, len(frame), len(frame)) + frame
        rows.append(
            {
                "frame.number": str(number),
                "frame.time_epoch": str(t),
                "frame.len": str(len(frame)),
                "ip.src": "172.31.0.8",
                "ip.dst": "172.31.0.3",
                "tcp.srcport": str(port),
                "tcp.dstport": "8883",
                "tcp.stream": str(index),
                "tcp.len": str(size),
                "tcp.flags": hex(flags),
                "tcp.window_size_value": "512",
                "tcp.time_delta": str(t - last.get(index, t)),
                "ip.proto": "6",
                "tcp.analysis.lost_segment": "",
            }
        )
        last[index] = t
    (folder / "traffic.pcap").write_bytes(raw)
    with (folder / "headers.csv").open("w") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    def save(name, value):
        (folder / name).write_text(json.dumps(value, indent=2) + "\n")

    save(
        "capture.json",
        dict(
            schema_version=1,
            pcap_sha256=digest(folder / "traffic.pcap"),
            stats={"captured": len(rows), "dropped_by_kernel": 0},
            stop_reason="orchestrator_stop",
        ),
    )
    save(
        "extractor.json",
        dict(
            schema_version=1,
            pcap_sha256=digest(folder / "traffic.pcap"),
            csv_sha256=digest(folder / "headers.csv"),
        ),
    )
    save(
        "ground-truth.json",
        dict(
            schema_version=1,
            mode="CONTROLLED_LAB",
            synthetic_unit_fixture=True,
            experiment={
                "experiment_id": "capture",
                "scenario": kind,
                "interval": 0.5,
                "jitter": 0.01,
            },
            clock={"boundary_margin_seconds": 0.00005},
            connections=connections,
            errors=[],
            all_clients_stopped=True,
        ),
    )
    save("core.json", dict(schema_version=2, security_events=events))
    if broker_available:
        save(
            "broker-evidence.json",
            dict(schema_version=2, source="docker_mosquitto_log", sessions=sessions),
        )
    return folder


def derived(tmp_path, **kwargs):
    captures = tmp_path / "raw"
    fixture(captures, **kwargs)
    out = tmp_path / "derived"
    build(captures, out)
    return captures, out


def coherent_hashes(out):
    m = json.loads((out / "dataset.manifest.json").read_text())
    obs = pd.read_csv(out / "observations.csv", keep_default_na=False)
    known = pd.read_csv(out / "dataset.csv", keep_default_na=False)
    m.update(
        sha256=digest(out / "dataset.csv"),
        observations_sha256=digest(out / "observations.csv"),
        rows=len(known),
        observations=len(obs),
        unknown_excluded=len(obs) - len(known),
        class_counts={k: int(v) for k, v in known.attack_type.value_counts().items()},
        captures=int(known.capture_id.nunique()),
        sessions=int(known.session_id.nunique()),
    )
    (out / "dataset.manifest.json").write_text(json.dumps(m, indent=2) + "\n")


def test_public_pipeline_positive_mixed_and_unknown(tmp_path):
    raw, out = derived(tmp_path)
    before = {str(p): digest(p) for root in [raw, out] for p in root.rglob("*") if p.is_file()}
    report = reconcile(out, raw)
    from src.research_stand.dataset import validate

    assert validate(out, raw)["reconciliation"] == "matched"
    with pytest.raises(ValueError, match="Raw capture evidence required"):
        validate(out)
    assert before == {
        str(p): digest(p) for root in [raw, out] for p in root.rglob("*") if p.is_file()
    }
    assert set(report["class_counts"]) == {"normal", "controlled_violation", "unknown"}
    f = pd.read_csv(out / "observations.csv", keep_default_na=False)
    assert set(f.label_unit) == {"connection_activity"} and set(f.packet_specific_evidence) == {
        "none_encrypted_tls"
    }
    assert f.loc[f.ground_truth == "controlled_violation", "authenticated_device"].eq("").all()


@pytest.mark.parametrize(
    "mutation",
    [
        "normal_to_violation",
        "violation_to_normal",
        "unknown_to_normal",
        "drop",
        "extra",
        "packet_identity",
        "connection",
        "reason",
        "capture",
        "time",
    ],
)
def test_coherent_hash_tampering_is_rejected(tmp_path, mutation):
    raw, out = derived(tmp_path)
    a = pd.read_csv(out / "observations.csv", keep_default_na=False)
    if mutation in ["normal_to_violation", "violation_to_normal", "unknown_to_normal"]:
        old = {
            "normal_to_violation": "normal",
            "violation_to_normal": "controlled_violation",
            "unknown_to_normal": "unknown",
        }[mutation]
        new = "controlled_violation" if mutation == "normal_to_violation" else "normal"
        i = a.index[a.ground_truth == old][0]
        a.loc[i, ["ground_truth", "attack_type", "label"]] = [
            new,
            "Normal" if new == "normal" else "ControlledViolation",
            "0" if new == "normal" else "1",
        ]
    elif mutation == "drop":
        a = a.iloc[1:]
    elif mutation == "extra":
        r = a.iloc[[1]].copy()
        r["packet_id"] = "lightcrypto-lab-fixed:capture:999"
        a = pd.concat([a, r])
    elif mutation == "packet_identity":
        a.loc[1, "packet_id"] = "lightcrypto-lab-fixed:capture:999"
    elif mutation == "connection":
        a.loc[1, "connection_id"] = "forged-connection"
    elif mutation == "reason":
        a.loc[1, "label_reason"] = "forged-proof"
    elif mutation == "capture":
        a.loc[1, "capture_id"] = "foreign:capture"
    else:
        a.loc[1, "epoch_seconds"] = float(a.loc[1, "epoch_seconds"]) + 0.1
    a.to_csv(out / "observations.csv", index=False)
    a.loc[a.ground_truth != "unknown"].to_csv(out / "dataset.csv", index=False)
    coherent_hashes(out)
    expected = {
        "normal_to_violation": "ground_truth",
        "violation_to_normal": "ground_truth",
        "unknown_to_normal": "ground_truth",
        "drop": "Missing/extra observation",
        "extra": "Missing/extra observation",
        "packet_identity": "packet_id",
        "connection": "connection_id",
        "reason": "label_reason",
        "capture": "capture_id",
        "time": "timestamp",
    }[mutation]
    with pytest.raises(ValueError, match=expected):
        reconcile(out, raw)


@pytest.mark.parametrize("kind", ["bounded_rate", "pattern_change"])
@pytest.mark.parametrize(
    "case",
    [
        "unchanged",
        "few",
        "missing_broker",
        "tcp_retransmissions_only",
        "packet_size_only",
        "ambiguous_boundary",
    ],
)
def test_unverified_behavior_never_positive_through_public_pipeline(tmp_path, kind, case):
    raw = tmp_path / "raw"
    folder = fixture(
        raw,
        kind=kind,
        changed=case not in ["unchanged", "tcp_retransmissions_only", "packet_size_only"],
        few=case == "few",
        broker_available=case != "missing_broker",
        tcp_variant=case if case in ["tcp_retransmissions_only", "packet_size_only"] else None,
    )
    # Packet size/retransmission annotations alone do not supply MQTT events.
    if case in ["tcp_retransmissions_only", "packet_size_only"]:
        core = json.loads((folder / "core.json").read_text())
        core["tcp_only_diagnostic"] = case
        (folder / "core.json").write_text(json.dumps(core))
    if case == "ambiguous_boundary":
        truth = json.loads((folder / "ground-truth.json").read_text())
        truth["clock"]["boundary_margin_seconds"] = 10
        (folder / "ground-truth.json").write_text(json.dumps(truth))
    out = tmp_path / "out"
    build(raw, out)
    f = pd.read_csv(out / "observations.csv", keep_default_na=False)
    assert not (f.ground_truth == "controlled_violation").any()


@pytest.mark.parametrize("kind", ["bounded_rate", "pattern_change"])
def test_observed_behavior_and_normal_neighbors(tmp_path, kind):
    raw, out = derived(tmp_path, kind=kind)
    f = pd.read_csv(out / "observations.csv", keep_default_na=False)
    assert (f.ground_truth == "controlled_violation").any()
    assert set(f.loc[f.ground_truth == "controlled_violation", "connection_id"]) == {"connection-1"}
    assert (
        f.loc[(f.connection_id == "connection-0") & (f.ground_truth != "unknown"), "ground_truth"]
        .eq("normal")
        .all()
    )
    assert reconcile(out, raw)["corroborated_connections"] == 2


def test_no_syn_pipeline_cannot_attribute(tmp_path):
    _, out = derived(tmp_path, no_syn=True)
    assert pd.read_csv(out / "observations.csv").ground_truth.eq("unknown").all()


def test_generator_flag_cannot_replace_broker_result(tmp_path):
    raw = tmp_path / "raw"
    folder = fixture(raw)
    p = folder / "broker-evidence.json"
    e = json.loads(p.read_text())
    e["sessions"][1]["auth_code"] = 0
    p.write_text(json.dumps(e))
    out = tmp_path / "out"
    build(raw, out)
    f = pd.read_csv(out / "observations.csv")
    assert not f.ground_truth.eq("controlled_violation").any()


def test_real_capture_provenance_is_not_scientific_proof():
    s = statuses(
        dict(
            schema_version=1,
            synthetic=False,
            label_scope="packet_audited",
            provenance={
                "real_packet_capture": True,
                "generated_test_clients": True,
                "controlled_lab_scenarios": True,
            },
        )
    )
    assert (
        not s["scientific_quality_available"]
        and not s["laboratory_labels_validated"]
        and s["independent_external_validation_pending"]
        and s["real_attack_detection_unproven"]
    )


def test_absent_broker_source_makes_every_connection_unknown(tmp_path):
    _, out = derived(tmp_path, broker_available=False)
    assert pd.read_csv(out / "observations.csv").ground_truth.eq("unknown").all()


def test_broker_parser_distinguishes_same_client_reconnect_endpoints():
    from src.research_stand.broker_evidence import parse

    cid = "lab-" + "a" * 32
    lines = [
        f"2026-11-10T00:00:00.000Z 1: New connection from 172.31.0.8:40000 on port 8883.",
        f"2026-11-10T00:00:00.010Z 1: New client connected from 172.31.0.8:40000 as {cid} (p4, c0, k30, u'device_lab001').",
        f"2026-11-10T00:00:00.020Z 1: Client {cid} [172.31.0.8:40000] disconnected: connection closed by client.",
        f"2026-11-10T00:00:00.021Z 1: New connection from 172.31.0.8:41000 on port 8883.",
        f"2026-11-10T00:00:00.030Z 1: New client connected from 172.31.0.8:41000 as {cid} (p4, c0, k30, u'device_lab001').",
        f"2026-11-10T00:00:00.040Z 1: Received PUBLISH from {cid} (d1, q1, r0, m1, 'iot/sensors/lab001', ... (400 bytes))",
    ]
    result = parse("\n".join(lines), 0, 9999999999)
    assert len(result["sessions"]) == 2 and result["sessions"][0]["closed_at"]
    assert result["sessions"][1]["events"][0]["dup"] == 1


def test_quality_flags_cannot_replace_source_evidence(tmp_path):
    raw, out = derived(tmp_path, broker_available=False)
    p = out / "dataset.manifest.json"
    m = json.loads(p.read_text())
    m["provenance"]["independent_label_verification"] = True
    m["data_quality"]["scientific_quality_available"] = True
    p.write_text(json.dumps(m))
    with pytest.raises(ValueError, match="scientific|corroborated"):
        reconcile(out, raw)


def test_parallel_pending_health_connection_does_not_hide_auth_denial():
    from src.research_stand.broker_evidence import parse

    cid = "lab-" + "b" * 32
    lines = [
        "2026-11-10T00:00:00.000Z 1: New connection from 172.31.0.2:42000 on port 8883.",
        "2026-11-10T00:00:00.010Z 1: New connection from 172.31.0.8:40000 on port 8883.",
        f"2026-11-10T00:00:00.020Z 1: Sending CONNACK to {cid} (0, 5)",
        f"2026-11-10T00:00:00.021Z 1: Client {cid} [172.31.0.8:40000] disconnected: not authorised.",
    ]
    report = parse("\n".join(lines), 0, 9999999999)
    assert len(report["sessions"]) == 1 and report["sessions"][0]["auth_code"] == 5
    assert report["sessions"][0]["port"] == 40000 and report["sessions"][0]["username"] is None


def test_forged_source_stream_with_coherent_export_hash_is_rejected(tmp_path):
    raw = tmp_path / "raw"
    folder = fixture(raw)
    with (folder / "headers.csv").open() as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["tcp.stream"] = str(int(r["tcp.stream"]) + 50)
    with (folder / "headers.csv").open("w") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    p = folder / "extractor.json"
    m = json.loads(p.read_text())
    m["csv_sha256"] = digest(folder / "headers.csv")
    p.write_text(json.dumps(m))
    with pytest.raises(ValueError, match="stream identity"):
        build(raw, tmp_path / "out")


def test_generator_cannot_extend_activity_past_independent_session_end(tmp_path):
    raw = tmp_path / "raw"
    folder = fixture(raw)
    p = folder / "broker-evidence.json"
    b = json.loads(p.read_text())
    for s in b["sessions"]:
        s["closed_at"] = 8.0
    p.write_text(json.dumps(b))
    out = tmp_path / "out"
    build(raw, out)
    f = pd.read_csv(out / "observations.csv")
    assert f.loc[f.epoch_seconds == 8.8, "ground_truth"].eq("unknown").all()


def test_nonfinite_source_clock_is_not_silently_accepted(tmp_path):
    raw = tmp_path / "raw"
    folder = fixture(raw)
    p = folder / "ground-truth.json"
    t = json.loads(p.read_text())
    t["clock"]["boundary_margin_seconds"] = float("nan")
    p.write_text(json.dumps(t))
    with pytest.raises(ValueError, match="Nonfinite"):
        build(raw, tmp_path / "out")


def test_copied_pcap_cannot_inflate_independent_capture_support(tmp_path):
    import shutil

    raw = tmp_path / "raw"
    source = fixture(raw)
    clone = raw / "renamed"
    shutil.copytree(source, clone)
    p = clone / "ground-truth.json"
    t = json.loads(p.read_text())
    t["experiment"]["experiment_id"] = "renamed"
    p.write_text(json.dumps(t))
    with pytest.raises(ValueError, match="Duplicate source PCAP"):
        build(raw, tmp_path / "out")

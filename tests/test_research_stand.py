"""Synthetic engineering fixtures only; no scientific IDS quality claims."""

import copy, json
import pytest
from src.research_stand.config import Experiment
from src.research_stand.ground_truth import map_packets as raw_map_packets


def map_packets(rows, truth, broker, core):
    return raw_map_packets(rows, truth, broker, {"accepted_devices": ["lab001"], **core})


from src.research_stand.orchestrator import matrix
from src.classifier.research.datasets import ONTOLOGIES


def fixture():
    rows = []
    for n, t, flags in [(1, 1, "0x0002"), (2, 2, "0x0018"), (3, 3, "0x0010"), (4, 4, "0x0011")]:
        rows.append(
            {
                "frame.number": str(n),
                "frame.time_epoch": str(t),
                "ip.src": "172.31.0.8",
                "ip.dst": "172.31.0.3",
                "tcp.srcport": "40000",
                "tcp.dstport": "8883",
                "tcp.stream": "0",
                "tcp.flags": flags,
            }
        )
    r = dict(
        connection_id="one",
        local_ip="172.31.0.8",
        local_port=40000,
        remote_ip="172.31.0.3",
        remote_port=8883,
        tls_open_at=1.5,
        closed_at=3.5,
        activity="normal",
        confirmed=True,
        authenticated=True,
        logical_device="lab001",
        actions=[],
    )
    return rows, dict(clock={"boundary_margin_seconds": 0.001}, connections=[r])


@pytest.mark.parametrize(
    "field,value",
    [
        ("clients", 25),
        ("clients", True),
        ("duration", 21),
        ("interval", 0.01),
        ("jitter", float("nan")),
        ("seed", -1),
        ("experiment_id", "../bad"),
        ("violation", 1),
        ("scenario", "arbitrary_target"),
    ],
)
def test_bounds(field, value):
    with pytest.raises((ValueError, TypeError)):
        Experiment(**{**dict(experiment_id="test", scenario="regular"), field: value}).validate()


def test_matrix_paired_background_and_unique_runs():
    m = matrix(60, "test")
    assert len({c.experiment_id for c in m}) == 60
    for a, b in zip(m[::2], m[1::2]):
        assert (a.seed, a.clients, a.duration, a.interval) == (
            b.seed,
            b.clients,
            b.duration,
            b.interval,
        )
        assert not a.violation and b.violation
        a.validate()
        b.validate()


def test_boundary_and_normal():
    rows, truth = fixture()
    result = map_packets(rows, truth, {}, {})
    assert [r["ground_truth"] for r in result] == ["unknown", "normal", "normal", "unknown"]


def test_mixed_capture_has_both_labels():
    rows, truth = fixture()
    other = copy.deepcopy(truth["connections"][0])
    other.update(
        connection_id="two",
        local_port=41000,
        activity="bad_credentials",
        authenticated=False,
        auth_rejected=True,
    )
    truth["connections"].append(other)
    extra = [
        {
            **r,
            "tcp.stream": "1",
            "tcp.srcport": "41000",
            "frame.number": str(int(r["frame.number"]) + 4),
        }
        for r in rows
    ]
    out = map_packets(rows + extra, truth, {}, {})
    assert set(r["ground_truth"] for r in out) == {"unknown", "normal", "controlled_violation"}
    assert all(
        not r["authenticated_device"] for r in out if r["ground_truth"] == "controlled_violation"
    )


def test_time_only_does_not_label():
    rows, truth = fixture()
    truth["connections"][0]["local_port"] = 50000
    assert {r["ground_truth"] for r in map_packets(rows, truth, {}, {})} == {"unknown"}


def test_reused_tuple_is_ambiguous():
    rows, truth = fixture()
    truth["connections"].append({**truth["connections"][0], "connection_id": "two"})
    assert {r["ground_truth"] for r in map_packets(rows, truth, {}, {})} == {"unknown"}


def test_no_syn_is_unknown():
    rows, truth = fixture()
    assert {r["ground_truth"] for r in map_packets(rows[1:], truth, {}, {})} == {"unknown"}


@pytest.mark.parametrize(
    "activity,extra,core,broker,expected",
    [
        ("forbidden_acl", {}, {}, {}, "unknown"),
        (
            "forbidden_acl",
            {"client_id": "lab-a"},
            {},
            {"acl_denied_clients": ["lab-a"]},
            "controlled_violation",
        ),
        (
            "replay",
            {"actions": [{"sequence_number": 1, "key_epoch": 1}]},
            {"replay_identities": [["lab001", 1, 1]]},
            {},
            "controlled_violation",
        ),
        ("tampered", {"local_crypto_rejection": True}, {"rejected_delta": 0}, {}, "unknown"),
        (
            "tampered",
            {"local_crypto_rejection": True},
            {"rejected_delta": 1},
            {},
            "controlled_violation",
        ),
    ],
)
def test_independent_outcome_required(activity, extra, core, broker, expected):
    rows, truth = fixture()
    truth["connections"][0].update(activity=activity, **extra)
    assert map_packets(rows, truth, broker, core)[1]["ground_truth"] == expected


def test_qos_retry_is_normal_even_if_replay_count_increases():
    rows, truth = fixture()
    truth["connections"][0]["normal_retry_dup_observed"] = True
    assert (
        map_packets(
            rows, truth, {}, {"rejected_delta": 1, "replay_identities": [["lab001", 1, 1]]}
        )[1]["ground_truth"]
        == "normal"
    )


def test_private_ontology_separate_from_real_attack_datasets():
    assert ONTOLOGIES["lightcrypto-lab-v1"] == ["ControlledViolation", "Normal"]
    assert "ControlledViolation" not in ONTOLOGIES["mqttset"]


def test_normal_requires_verified_acceptance():
    rows, truth = fixture()
    assert {r["ground_truth"] for r in raw_map_packets(rows, truth, {}, {})} == {"unknown"}


def test_builder_keeps_unknown_out_of_training_and_preserves_provenance(tmp_path, monkeypatch):
    from src.research_stand import dataset as module
    from src.classifier.research.datasets import read_prepared

    root = tmp_path / "captures"
    folder = root / "fixture"
    folder.mkdir(parents=True)
    (folder / "ground-truth.json").write_text("{}")
    (folder / "core.json").write_text(
        json.dumps(dict(categories={}, before={"categories": {}}, mongo_delta=2, outbox_pending=0))
    )
    rows, truth = fixture()
    for r in rows:
        r.update(
            {
                "frame.len": "120",
                "tcp.len": "60",
                "tcp.window_size_value": "512",
                "tcp.time_delta": "0.1",
                "tcp.analysis.lost_segment": "",
            }
        )
    labeled = map_packets(rows, truth, {}, {})
    truth.update(
        experiment=Experiment("fixture", "regular").payload(),
        devices=["lab001"],
        experiment_started_at=1,
        experiment_finished_at=4,
        sent_messages=2,
        generator_peak_rss_kib=1024,
    )
    truth["connections"][0]["normal_retry_dup_observed"] = False
    cap = dict(
        pcap_sha256="a" * 64,
        bytes=500,
        stats={"dropped_by_kernel": 0},
        tcpdump_version="synthetic fixture",
        collector_peak_rss_kib=1024,
    )
    monkeypatch.setattr(
        module, "read", lambda _: (labeled, truth, cap, {"tool_version": "synthetic fixture"})
    )
    output = tmp_path / "dataset"
    report = module.build(root, output)
    assert report["unknown_rows"] == 2 and report["known_rows"] == 2
    frame, manifest = read_prepared(output / "dataset.csv", output / "dataset.manifest.json")
    assert set(frame.label) == {0} and frame.experiment_id.eq("fixture").all()
    assert manifest["feature_order"] == module.FEATURES
    assert module.validate(output, root)["known_rows"] == 2
    (folder / "ground-truth.json").write_text("modified")
    with pytest.raises(ValueError, match="integrity"):
        module.validate(output, root)
    with pytest.raises(ValueError, match="immutable"):
        module.build(root, output)


def test_capture_hash_tampering_rejected_before_labels(tmp_path):
    from src.research_stand.dataset import read

    (tmp_path / "traffic.pcap").write_bytes(b"synthetic invalid capture")
    (tmp_path / "capture.json").write_text(json.dumps({"pcap_sha256": "0" * 64}))
    (tmp_path / "extractor.json").write_text("{}")
    (tmp_path / "ground-truth.json").write_text("{}")
    with pytest.raises(ValueError, match="hash mismatch"):
        read(tmp_path)


def test_unknown_does_not_become_normal_when_no_outcome():
    rows, truth = fixture()
    truth["connections"][0].update(activity="bounded_rate", actions=[{}])
    assert {r["ground_truth"] for r in map_packets(rows, truth, {}, {})} == {"unknown"}


def test_duplicate_connection_identity_rejected():
    rows, truth = fixture()
    truth["connections"] *= 2
    with pytest.raises(ValueError, match="Duplicate"):
        map_packets(rows, truth, {}, {})


def test_missing_clock_uncertainty_rejected():
    rows, truth = fixture()
    truth["clock"]["boundary_margin_seconds"] = float("nan")
    with pytest.raises(ValueError, match="clock"):
        map_packets(rows, truth, {}, {})


def test_disk_watchdog_refuses_oversized_volume():
    from src.research_stand.orchestrator import Lab

    lab = Lab.__new__(Lab)
    lab.call = lambda *a: str(2 * 1024**2) + " /private\n"
    with pytest.raises(ValueError, match="disk budget"):
        lab.resource_usage()


def test_retention_requires_explicit_safe_identity(tmp_path):
    from src.research_stand.retention import eligible

    with pytest.raises(ValueError):
        eligible(tmp_path, "../other", 30)
    outside = tmp_path / "outside"
    outside.mkdir()
    root = tmp_path / "root"
    root.mkdir()
    (root / "capture").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="Unsafe"):
        eligible(root, "capture", 30)


def test_explicit_exclusion_must_match_original_capture_hash(tmp_path):
    from src.research_stand.dataset import build

    root = tmp_path / "raw"
    folder = root / "fixture"
    folder.mkdir(parents=True)
    (folder / "ground-truth.json").write_text("{}")
    (folder / "traffic.pcap").write_bytes(b"synthetic")
    selection = tmp_path / "selection.json"
    selection.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "excluded": [
                    {
                        "capture_id": "fixture",
                        "pcap_sha256": "0" * 64,
                        "reason": "synthetic unit test exclusion",
                    }
                ],
            }
        )
    )
    with pytest.raises(ValueError, match="exclusion source mismatch"):
        build(root, tmp_path / "out", selection)


def test_retention_is_only_an_age_check_without_deletion(tmp_path):
    from src.research_stand.retention import eligible
    from src.research_stand.collector import sha

    folder = tmp_path / "fixture"
    folder.mkdir()
    pcap = folder / "traffic.pcap"
    pcap.write_bytes(b"synthetic")
    (folder / "capture.json").write_text(json.dumps({"pcap_sha256": sha(pcap)}))
    (folder / "ground-truth.json").write_text(
        json.dumps({"experiment": {"experiment_id": "fixture"}, "experiment_finished_at": 100})
    )
    assert not eligible(tmp_path, "fixture", 30, now=200)
    assert eligible(tmp_path, "fixture", 30, now=100 + 31 * 86400)
    assert pcap.exists()


def test_invalid_test_credential_keeps_legitimate_length():
    from src.research_stand.install import invalid_password

    assert len(invalid_password(48)) == 48
    assert any(c not in "0123456789abcdef" for c in invalid_password(48))
    with pytest.raises(ValueError):
        invalid_password(0)


def test_header_exports_are_private_even_with_permissive_parent_umask(tmp_path, monkeypatch):
    import os, stat
    from src.research_stand import collector

    (tmp_path / "traffic.pcap").write_bytes(b"synthetic fixture, not real network data")
    monkeypatch.setattr(
        collector.subprocess,
        "run",
        lambda cmd, stdout, **kwargs: stdout.write("synthetic header\n"),
    )
    monkeypatch.setattr(
        collector.subprocess, "check_output", lambda *a, **k: "synthetic tool fixture\n"
    )
    previous = os.umask(0o022)
    try:
        collector.extract(tmp_path)
        assert stat.S_IMODE((tmp_path / "headers.csv").stat().st_mode) == 0o600
        assert stat.S_IMODE((tmp_path / "extractor.json").stat().st_mode) == 0o600
    finally:
        os.umask(previous)

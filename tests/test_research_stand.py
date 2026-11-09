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

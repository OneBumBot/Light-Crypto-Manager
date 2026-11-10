"""Immutable private laboratory dataset, independently checked against capture manifests."""

import argparse, csv, json, os, hashlib, math
from pathlib import Path
from collections import Counter
import pandas as pd
from src.classifier.research.schema import FEATURES, VERSION, packet_frame
from .collector import sha
from .ground_truth import map_packets


def read(folder):
    def j(name):
        return json.loads((folder / name).read_text())

    capture = j("capture.json")
    extractor = j("extractor.json")
    truth = j("ground-truth.json")
    if (
        capture["pcap_sha256"] != sha(folder / "traffic.pcap")
        or extractor["pcap_sha256"] != capture["pcap_sha256"]
        or extractor["csv_sha256"] != sha(folder / "headers.csv")
    ):
        raise ValueError("Capture/extractor hash mismatch")
    for item in [capture, extractor, truth]:
        if type(item.get("schema_version")) is not int or item["schema_version"] != 1:
            raise ValueError("Unsupported capture journal schema")
    if truth.get("mode") != "CONTROLLED_LAB":
        raise ValueError("Unverified ground truth origin")
    if (
        extractor["feature_version"] != VERSION
        or extractor["extractor_version"] != "lcm-tshark-tcp-v1"
    ):
        raise ValueError("Unsupported extractor")
    if capture["link_layer_type"] != 1:
        raise ValueError("Unverified link layer")
    if capture["stats"]["dropped_by_kernel"] != 0:
        raise ValueError("Capture loss or unavailable loss counter; quarantine")
    if capture["stop_reason"] not in ["duration", "orchestrator_stop"]:
        raise ValueError("Capture resource/failure limit reached; quarantine")
    if (
        truth["errors"]
        or not truth["all_clients_stopped"]
        or any(r.get("closed_at") is None for r in truth["connections"])
    ):
        raise ValueError("Incomplete generator run; quarantine")
    with (folder / "headers.csv").open() as f:
        rows = list(csv.DictReader(f))
    if len(rows) > 20000 or not rows:
        raise ValueError("Empty/oversize capture")
    if len(rows) != capture["stats"]["captured"]:
        raise ValueError("PCAP/export packet count conflict")
    numbers = [r["frame.number"] for r in rows]
    if len(set(numbers)) != len(numbers):
        raise ValueError("Repeated physical packet identity")
    times = [float(r["frame.time_epoch"]) for r in rows]
    if not all(math.isfinite(t) and t > 0 for t in times):
        raise ValueError("Invalid timestamps")
    if any(a - b > 0.005 for a, b in zip(times, times[1:])):
        raise ValueError("Clock reversal exceeds5ms; quarantine")
    # All five definitions come from tshark; no missing-to-zero substitution.
    if any(any(r.get(k, "") == "" for k in FEATURES) for r in rows):
        raise ValueError("Missing feature value; quarantine")
    packet_frame(pd.DataFrame(rows))
    labeled = map_packets(rows, truth, j("broker-events.json"), j("core.json"))
    return labeled, truth, capture, extractor


def build(root, output, selection=None):
    os.umask(0o077)
    root = Path(root)
    output = Path(output)
    if output.exists():
        raise ValueError("Dataset directory immutable")
    captures = sorted(
        p for p in root.iterdir() if p.is_dir() and (p / "ground-truth.json").exists()
    )
    if not captures or len(captures) > 100:
        raise ValueError("Bounded1..100 completed captures required")
    excluded = []
    selection = (
        json.loads(Path(selection).read_text())
        if selection
        else {"schema_version": 1, "excluded": []}
    )
    if selection.get("schema_version") != 1 or not isinstance(selection.get("excluded"), list):
        raise ValueError("Invalid curation declaration")
    excluded_ids = set()
    for item in selection["excluded"]:
        identity = item["capture_id"]
        if identity in excluded_ids or Path(identity).name != identity or not item.get("reason"):
            raise ValueError("Explicit unique exclusion reason required")
        folder = root / identity
        if sha(folder / "traffic.pcap") != item["pcap_sha256"]:
            raise ValueError("Curated exclusion source mismatch")
        excluded_ids.add(identity)
        excluded.append(item)
    rows = []
    reports = []
    hashes = set()
    ids = set()
    quarantined = []
    for folder in captures:
        if folder.name in excluded_ids:
            continue
        try:
            labeled, truth, cap, ext = read(folder)
        except (ValueError, KeyError, FileNotFoundError) as e:
            quarantined.append(dict(capture_id=folder.name, reason=str(e)))
            continue
        if len(rows) + len(labeled) > 100000:
            raise ValueError(
                "Dataset build resource bound100000 observations; no silent truncation"
            )
        identity = truth["experiment"]["experiment_id"]
        if identity != folder.name or identity in ids or cap["pcap_sha256"] in hashes:
            raise ValueError("Duplicate/conflicting capture identity")
        ids.add(identity)
        hashes.add(cap["pcap_sha256"])
        source = "lightcrypto-lab-75b"
        capture = source + ":" + identity
        counts = Counter(r["ground_truth"] for r in labeled)
        for r in labeled:
            row = {k: r[k] for k in FEATURES}
            row.update(
                source_id=source,
                capture_id=capture,
                experiment_id=identity,
                session_id=capture + ":" + r["tcp.stream"],
                packet_id=capture + ":" + r["frame.number"],
                epoch_seconds=float(r["frame.time_epoch"]),
                feature_version=VERSION,
                ground_truth=r["ground_truth"],
                label_source="controlled_orchestrator+socket+outcome",
                label_confidence=r["label_confidence"],
                label_reason=r["label_reason"],
                connection_id=r["connection_id"],
                direction=r["direction"],
                authenticated_device=r["authenticated_device"],
                source_pcap_sha256=cap["pcap_sha256"],
                scenario_category=truth["experiment"]["scenario"],
                attack_type="Normal"
                if r["ground_truth"] == "normal"
                else "ControlledViolation"
                if r["ground_truth"] == "controlled_violation"
                else "Unknown",
                label=0
                if r["ground_truth"] == "normal"
                else 1
                if r["ground_truth"] == "controlled_violation"
                else None,
            )
            rows.append(row)
        reports.append(
            dict(
                capture_id=identity,
                config=truth["experiment"],
                devices=len(truth["devices"]),
                connections=len(truth["connections"]),
                packets=len(labeled),
                class_counts=dict(counts),
                pcap_bytes=cap["bytes"],
                pcap_sha256=cap["pcap_sha256"],
                input_hashes={p.name: sha(p) for p in folder.iterdir() if p.is_file()},
                dropped_by_kernel=cap["stats"]["dropped_by_kernel"],
                tcp_sequence_gap_packets=sum(bool(r["tcp.analysis.lost_segment"]) for r in labeled),
                timestamp_reorder_pairs=sum(
                    float(a["frame.time_epoch"]) > float(b["frame.time_epoch"])
                    for a, b in zip(labeled, labeled[1:])
                ),
                duration=truth["experiment_finished_at"] - truth["experiment_started_at"],
                sent_messages=truth["sent_messages"],
                clock=truth["clock"],
                tcpdump_version=cap["tcpdump_version"],
                tshark_version=ext["tool_version"],
                generator_peak_rss_kib=truth["generator_peak_rss_kib"],
                qos_retry_dup_connections=sum(
                    r["normal_retry_dup_observed"] for r in truth["connections"]
                ),
            )
        )
    if not rows:
        raise ValueError("No valid observations; " + str(quarantined))
    output.mkdir(parents=True, mode=0o700)
    data = pd.DataFrame(rows)
    features = packet_frame(data)
    data[FEATURES] = features[FEATURES]
    data.to_csv(output / "observations.csv", index=False)
    known = data.loc[data.label.notna()].copy()
    known["label"] = known.label.astype(int)
    if len(known) == 0:
        raise ValueError("No verified observations")
    known.to_csv(output / "dataset.csv", index=False)
    manifest = dict(
        schema_version=1,
        feature_version=VERSION,
        granularity="packet",
        extractor="lcm-tshark-tcp-v1",
        synthetic=False,
        data_origin="controlled laboratory: generated clients, real TLS network packets",
        synthetic_sensor_values=True,
        source_url="local isolated LightCrypto MQTT/TLS lab",
        dataset_version="75b-v1",
        license="Private laboratory data; publication not authorized",
        label_scope="packet_audited",
        dataset_family="lightcrypto-lab-v1",
        class_ontology=["ControlledViolation", "Normal"],
        sha256=sha(output / "dataset.csv"),
        rows=len(known),
        feature_order=FEATURES,
        columns=list(known),
        captures=int(known.capture_id.nunique()),
        sessions=int(known.session_id.nunique()),
        class_counts={k: int(v) for k, v in known.attack_type.value_counts().items()},
        observations_sha256=sha(output / "observations.csv"),
        unknown_excluded=int(data.label.isna().sum()),
        raw_files=reports,
        quarantined=quarantined,
        curated_exclusions=excluded,
        limitations=[
            "Controlled lab violations, not representative real attacks; labels refer to connection activity, not malicious content of each packet",
            "Repeated runs on one host do not prove statistical independence; paired background, same device pool and capture method reduce but do not eliminate shortcuts",
            "Bad credentials do not authenticate a device. Tamper confirmation combines local invalid AEAD proof with aggregate isolated receiver reject; no attacker claimed device binding",
            "Captures collected after stage6/7.5, no old test reuse. No online IDS collector or trusted model activation.",
        ],
    )
    (output / "dataset.manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    validation = validate(output)
    (output / "validation.json").write_text(json.dumps(validation, indent=2) + "\n")
    for p in output.iterdir():
        p.chmod(0o600)
    return validation


def validate(directory, captures_root=None):
    from src.classifier.research.datasets import read_prepared

    directory = Path(directory)
    from .pcap_audit import load_json

    versioned = load_json(directory / "dataset.manifest.json")
    if versioned.get("label_rules_version"):
        if captures_root is None:
            raise ValueError("Raw capture evidence required for versioned label validation")
        from .label_verification import reconcile

        return reconcile(directory, captures_root)
    data, manifest = read_prepared(
        directory / "dataset.csv", directory / "dataset.manifest.json", max_rows=1000000
    )
    observations = pd.read_csv(directory / "observations.csv", keep_default_na=False)
    if sha(directory / "observations.csv") != manifest["observations_sha256"]:
        raise ValueError("Observation hash mismatch")
    if len(observations) - len(data) != manifest["unknown_excluded"]:
        raise ValueError("Unknown exclusion mismatch")
    if (
        set(data.ground_truth) - {"normal", "controlled_violation"}
        or not (data.label_source == "controlled_orchestrator+socket+outcome").all()
    ):
        raise ValueError("Unverified labels leaked")
    if not (data.label_confidence == "verified").all():
        raise ValueError("Ambiguous labels leaked")
    for k in ["connection_id", "source_pcap_sha256", "label_reason"]:
        if data[k].isna().any():
            raise ValueError("Incomplete label evidence")
    if captures_root is not None:
        for capture in manifest["raw_files"]:
            folder = Path(captures_root) / capture["capture_id"]
            for name, digest in capture["input_hashes"].items():
                if Path(name).name != name or sha(folder / name) != digest:
                    raise ValueError("Source capture integrity mismatch")
            read(folder)
        for capture in manifest.get("curated_exclusions", []):
            if (
                sha(Path(captures_root) / capture["capture_id"] / "traffic.pcap")
                != capture["pcap_sha256"]
            ):
                raise ValueError("Excluded source integrity mismatch")
        from .label_verification import legacy_reconcile

        reconciliation = legacy_reconcile(directory, captures_root)
    else:
        reconciliation = {
            "reconciliation": "not_performed_without_raw",
            "independent_label_verification": False,
        }
    # No identifiers or raw MQTT fields can enter model inputs.
    if manifest["feature_order"] != FEATURES:
        raise ValueError("Provenance became predictive feature")
    support = {
        str(label): int(data.loc[data.label == label, "capture_id"].nunique()) for label in [0, 1]
    }
    vectors = data.duplicated(FEATURES, keep=False)
    conflicts = data.groupby(FEATURES, dropna=False).label.nunique().gt(1).sum()
    by_class = {
        str(k): {
            f: {"mean": float(g[f].mean()), "std": float(g[f].std()) if len(g) > 1 else 0.0}
            for f in FEATURES
        }
        for k, g in data.groupby("label")
    }
    return dict(
        schema_version=1,
        status="engineering_validated_scientific_quality_unproven",
        label_reconciliation=reconciliation,
        observations=len(observations),
        known_rows=len(data),
        unknown_rows=manifest["unknown_excluded"],
        unknown_fraction=manifest["unknown_excluded"] / len(observations),
        captures=manifest["captures"],
        class_capture_support=support,
        class_counts=manifest["class_counts"],
        duplicate_vector_rows=int(vectors.sum()),
        conflicting_vectors=int(conflicts),
        feature_distributions=by_class,
        shortcut_review=[
            "Same device pool/config ranges for paired normal and mixed runs; identifiers excluded from five features",
            "Short auth/ACL sessions and deterministic software TCP stack can create trivial shortcuts; later evaluate per-scenario and held-out host/device/load",
            "No statistical evidence of shortcut absence; final ML test deferred",
        ],
        quarantined=manifest["quarantined"],
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=["build", "validate"])
    p.add_argument("--root", required=True)
    p.add_argument("--output")
    p.add_argument("--captures")
    p.add_argument("--selection")
    p.add_argument(
        "--archive-v1", action="store_true", help="Explicit historical reproduction only"
    )
    a = p.parse_args()
    if a.command == "build" and a.selection and not a.archive_v1:
        p.error(
            "Use --archive-v1 for legacy selection or dataset_v2 --parent-manifest for reannotation"
        )
    print(
        json.dumps(
            (
                build(a.root, a.output, a.selection)
                if a.archive_v1
                else __import__("src.research_stand.dataset_v2", fromlist=["build"]).build(
                    a.root, a.output
                )
            )
            if a.command == "build"
            else validate(a.root, a.captures),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

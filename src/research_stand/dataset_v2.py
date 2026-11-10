"""Separate immutable reannotation. Archival v1 inputs/plans are never rewritten."""

import argparse, json, os, csv
from pathlib import Path
import pandas as pd
from .pcap_audit import headers, load_json, digest
from .labels_v2 import annotate, VERSION
from .label_verification import reconcile
from .quality import statuses

FEATURES = ["frame.len", "tcp.len", "tcp.flags", "tcp.window_size_value", "tcp.time_delta"]


def build(captures, output, parent_manifest=None):
    os.umask(0o077)
    captures = Path(captures)
    output = Path(output)
    if output.exists():
        raise ValueError("Immutable v2 output exists")
    parent = load_json(parent_manifest) if parent_manifest else None
    names = (
        [r["capture_id"] for r in parent["raw_files"]]
        if parent
        else sorted(
            p.name for p in captures.iterdir() if p.is_dir() and (p / "ground-truth.json").exists()
        )
    )
    if not 1 <= len(names) <= 100:
        raise ValueError("Bounded1..100 captures")
    data = []
    sources = []
    for name in names:
        if Path(name).name != name:
            raise ValueError("Unsafe capture identity")
        folder = captures / name
        rows, cap, ext = headers(folder)
        truth = load_json(folder / "ground-truth.json")
        core = load_json(folder / "core.json")
        if (
            truth["errors"]
            or not truth["all_clients_stopped"]
            or any(not r.get("closed_at") for r in truth["connections"])
        ):
            raise ValueError("Incomplete experiment")
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
        labeled = annotate(rows, truth, broker, core)
        if len(data) + len(labeled) > 100000:
            raise ValueError("Dataset bound100000")
        prefix = "lightcrypto-lab-fixed:" + name
        for r in labeled:
            item = {f: float(int(r[f], 0)) if f == "tcp.flags" else float(r[f]) for f in FEATURES}
            item.update({k: v for k, v in r.items() if k not in rows[0]})
            item.update(
                source_id="lightcrypto-lab-fixed",
                capture_id=prefix,
                experiment_id=name,
                session_id=prefix + ":" + r["tcp.stream"],
                packet_id=prefix + ":" + r["frame.number"],
                epoch_seconds=float(r["frame.time_epoch"]),
                feature_version="tcp-packet-passive-v1",
                source_pcap_sha256=cap["pcap_sha256"],
                scenario_category=truth["experiment"]["scenario"],
                label_source=VERSION,
                label={"normal": "0", "controlled_violation": "1", "unknown": ""}[
                    r["ground_truth"]
                ],
                attack_type={
                    "normal": "Normal",
                    "controlled_violation": "ControlledViolation",
                    "unknown": "Unknown",
                }[r["ground_truth"]],
            )
            data.append(item)
        sources.append(
            dict(
                capture_id=name,
                synthetic_fixture=truth.get("synthetic_unit_fixture", False),
                pcap_sha256=cap["pcap_sha256"],
                input_hashes={p.name: digest(p) for p in folder.iterdir() if p.is_file()},
            )
        )
    output.mkdir(mode=0o700, parents=True)
    frame = pd.DataFrame(data)
    known = frame.loc[frame.ground_truth != "unknown"]
    frame.to_csv(output / "observations.csv", index=False)
    known.to_csv(output / "dataset.csv", index=False)
    manifest = dict(
        schema_version=1,
        dataset_version="75b-fix-v2.1",
        label_rules_version=VERSION,
        feature_version="tcp-packet-passive-v1",
        feature_order=FEATURES,
        granularity="packet",
        label_unit="connection_activity",
        label_scope="connection_activity_and_window_behavior",
        label_evidence_level="session_or_window_corroboration_not_packet_attack",
        dataset_family="lightcrypto-lab-v1",
        class_ontology=["ControlledViolation", "Normal"],
        synthetic=any(x.get("synthetic_fixture", False) for x in sources),
        sha256=digest(output / "dataset.csv"),
        observations_sha256=digest(output / "observations.csv"),
        rows=len(known),
        observations=len(frame),
        unknown_excluded=int((frame.ground_truth == "unknown").sum()),
        raw_files=sources,
        captures=int(known.capture_id.nunique()),
        sessions=int(known.session_id.nunique()),
        class_counts={k: int(v) for k, v in known.attack_type.value_counts().items()},
        columns=list(frame),
        parent_dataset_sha256=parent["sha256"] if parent else None,
        parent_manifest_sha256=digest(parent_manifest) if parent else None,
        provenance=dict(
            real_packet_capture=not any(x.get("synthetic_fixture", False) for x in sources),
            generated_test_clients=True,
            controlled_lab_scenarios=True,
            independent_label_verification=False,
            external_validation_performed=False,
            attack_realism_scope="controlled_lab_connection_activity_only",
            known_shortcut_risks=[
                "single_host_and_stack",
                "connection_duration",
                "scenario_selection",
                "capture_batch",
            ],
        ),
        license="Private laboratory data; not authorized for publication",
    )
    path = output / "dataset.manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    report = reconcile(output, captures)
    manifest["provenance"]["independent_label_verification"] = (
        report["corroborated_connections"] > 0
    )
    manifest["data_quality"] = statuses(manifest)
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    (output / "reconciliation.json").write_text(json.dumps(report, indent=2) + "\n")
    if parent:
        old = pd.read_csv(Path(parent_manifest).parent / "observations.csv", keep_default_na=False)
        a = old.set_index(
            ["experiment_id", old.packet_id.str.rsplit(":", n=1).str[-1]]
        ).ground_truth
        b = frame.set_index(
            ["experiment_id", frame.packet_id.str.rsplit(":", n=1).str[-1]]
        ).ground_truth
        change = dict(
            parent_dataset_sha256=parent["sha256"],
            changed_labels=int((a != b).sum()),
            became_unknown=int(((a != "unknown") & (b == "unknown")).sum()),
            new_corroborated_observations=int(((a == "unknown") & (b != "unknown")).sum()),
            unknown_total=int((b == "unknown").sum()),
            reasons="Missing timed independent session evidence cannot be retroactively reconstructed; connection/window semantics v2",
        )
        (output / "label-changes.json").write_text(json.dumps(change, indent=2) + "\n")
    for p in output.iterdir():
        p.chmod(0o600)
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--captures", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--parent-manifest")
    a = p.parse_args()
    print(json.dumps(build(a.captures, a.output, a.parent_manifest), indent=2))

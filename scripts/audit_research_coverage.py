"""Aggregate coverage-only audit of frozen partitions; no model or predictions.
Does not change split/purge. Identical feature values are NOT physical duplicates.
"""

import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold
from src.classifier.research.schema import FEATURES, packet_frame
from src.classifier.research.datasets import read_prepared


def summary(frame, observations=None, configs=None):
    out = {}
    configs = configs or {}
    for scenario in sorted(
        set(frame.scenario_category)
        | (set(observations.scenario_category) if observations is not None else set())
    ):
        f = frame.loc[frame.scenario_category == scenario]
        a = (
            observations.loc[observations.scenario_category == scenario]
            if observations is not None
            else f
        )
        positive = f.loc[f.label == 1]
        runs = set(a.experiment_id)
        ok = set(positive.experiment_id)
        out[scenario] = dict(
            runs=len(runs),
            positive_confirmation_runs=len(ok),
            runs_without_positive=len(runs - ok),
            normal_rows=int((f.label == 0).sum()),
            positive_rows=len(positive),
            unknown_rows=int((a.ground_truth == "unknown").sum()),
            connections=int(a.connection_id.replace("", np.nan).nunique()),
            sessions=int(a.session_id.nunique()),
            unique_feature_vectors=len(f.drop_duplicates(FEATURES)),
            positive_unique_vectors=len(positive.drop_duplicates(FEATURES)),
            evidence_scope="historical labels only, not scientifically revalidated",
            notes="runs_without_positive is not missed attack rate; normal scenarios intentionally have no positive",
        )
    return out


def run(dataset, plan_path):
    dataset = Path(dataset)
    f, m = read_prepared(dataset / "dataset.csv", dataset / "dataset.manifest.json")
    obs = pd.read_csv(dataset / "observations.csv", keep_default_na=False)
    plan = json.loads(Path(plan_path).read_text())
    seed = plan["split"]["seed"]
    folds = list(
        StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed).split(
            f, f.label, f.capture_id
        )
    )
    test = folds[0][1]
    validation = folds[1][1]
    train = np.setdiff1d(np.arange(len(f)), np.r_[test, validation])
    before = [train, validation, test]
    raw = Path(".local-runtime/stand75b/primary")
    configs = {
        p.name: json.loads((p / "ground-truth.json").read_text())["experiment"]
        for p in raw.iterdir()
        if p.is_dir()
    }
    parts = {}
    seed_sets = []
    for name, index, final in zip(
        ["train", "validation", "test"], before, plan["split"]["indices"]
    ):
        a = f.iloc[index]
        b = f.iloc[final]
        seed_sets.append({configs[c]["seed"] for c in b.experiment_id.unique()})
        parts[name] = dict(
            before=summary(a),
            after=summary(b),
            rows_before=len(a),
            rows_after=len(b),
            positive_before=int(a.label.sum()),
            positive_after=int(b.label.sum()),
            prevalence_before=float(a.label.mean()),
            prevalence_after=float(b.label.mean()),
            captures_before=int(a.capture_id.nunique()),
            captures_after=int(b.capture_id.nunique()),
            zero_positive_scenarios=sorted(
                set(a.scenario_category) - set(b.loc[b.label == 1, "scenario_category"])
            ),
        )
    physical = int(obs.packet_id.duplicated().sum())
    cross = {
        a + "_" + b: len(seed_sets[i] & seed_sets[j])
        for a, b, i, j in [
            ("train", "validation", 0, 1),
            ("train", "test", 0, 2),
            ("validation", "test", 1, 2),
        ]
    }
    return dict(
        schema_version=1,
        scope="predeclared aggregate coverage audit only; no model outputs, tuning or test predictions",
        historical_dataset_sha256=m["sha256"],
        frozen_plan_sha256=plan["plan_sha256"],
        overall=summary(f, obs, configs),
        partitions=parts,
        physical_duplicate_packets=physical,
        repeated_network_events="QoS1 and deliberate replay are distinct events, not physical duplicates; see source journals",
        identical_feature_vectors_rows=int(f.duplicated(FEATURES, keep=False).sum()),
        feature_purge_rows=plan["split"]["duplicate_purged_rows"],
        condition_pair_seed_intersections=cross,
        conclusions=[
            "Existing purge removes equal five-field values, not proven duplicate physical events",
            "Capture/session disjointness does not imply condition-pair/device independence",
            "Old split remains unchanged; no replacement split or oversampling",
            "Some scenario coverage is absent after purge; no per-scenario efficacy can be claimed without support",
        ],
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", required=True)
    p.add_argument("--plan", required=True)
    p.add_argument("--output", required=True)
    a = p.parse_args()
    result = run(a.dataset, a.plan)
    with Path(a.output).open("x") as f:
        json.dump(result, f, indent=2)
        f.write("\n")
    print(
        json.dumps(
            {
                "physical_duplicates": result["physical_duplicate_packets"],
                "pair_seed_intersections": result["condition_pair_seed_intersections"],
                "test_coverage": result["partitions"]["test"]["after"],
            },
            indent=2,
        )
    )

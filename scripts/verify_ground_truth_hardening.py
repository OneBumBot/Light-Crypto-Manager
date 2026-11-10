"""Real service/TCP/TLS and source-tampering probes. Own lcm-stage7b-* project only.
No training/prediction. Copies never modify originals. Success requires assertions.
"""

import argparse, json, shutil, time, csv
from pathlib import Path
import pandas as pd
from src.research_stand.orchestrator import Lab
from src.research_stand.config import Experiment
from src.research_stand.dataset_v2 import build
from src.research_stand.label_verification import reconcile
from src.research_stand.pcap_audit import digest

PROBE = """
import json
from sqlalchemy import create_engine,text
from src.runtime import database_url
from src.mongo_repository import MongoRepository
engine=create_engine(database_url());repo=MongoRepository()
with engine.connect() as c:
 categories=dict(c.execute(text('SELECT category,count(*) FROM security_observations GROUP BY category')).all())
 pending=c.execute(text("SELECT count(*) FROM telemetry_outbox WHERE status!='delivered'")).scalar_one()
 total=c.execute(text('SELECT count(*) FROM telemetry_outbox')).scalar_one()
 assert c.execute(text("SELECT count(*) FROM security_observations WHERE category='rejected' AND device_id IS NOT NULL")).scalar_one()==0
 assert c.execute(text('SELECT count(*) FROM policy_device_states WHERE applied IS NOT NULL')).scalar_one()==0
 assert set(c.execute(text('SELECT DISTINCT mode FROM policy_worker_status')).scalars())=={'DRY_RUN'}
 assert all(categories.get(k,0)>0 for k in ['accepted','replay','rejected'])
 assert pending==0 and repo.collection.count_documents({})==total
 assert len(repo.collection.distinct('device_id'))>=4
print(json.dumps(dict(categories=categories,outbox_pending=pending,mongo_records=total,policy_mode='DRY_RUN',applied=0)))
repo.close();engine.dispose()
"""


def checks(env, captures, output):
    captures = Path(captures)
    output = Path(output)
    if output.exists():
        raise ValueError("Probe output immutable")
    output.mkdir(mode=0o700, parents=True)
    lab = Lab(env, output / "fault-output")
    time.sleep(2)
    source_before = {str(p): digest(p) for p in captures.rglob("*") if p.is_file()}
    service = json.loads(lab.call("run", "--rm", "-T", "--no-deps", "tests", "python", "-c", PROBE))
    data = output / "checked-dataset"
    reconciliation = build(captures, data)
    frame = pd.read_csv(data / "observations.csv", keep_default_na=False)
    outcomes = {}
    regular = frame.loc[frame.scenario_category == "regular"]
    assert (
        not regular.empty
        and regular.ground_truth.ne("controlled_violation").all()
        and regular.ground_truth.eq("normal").any()
    )
    outcomes["A_normal_tls"] = dict(
        status="passed",
        normal=int(regular.ground_truth.eq("normal").sum()),
        server_records=service["mongo_records"],
    )
    for kind in ["forbidden_acl", "replay", "bounded_rate", "pattern_change", "bad_credentials"]:
        part = frame.loc[frame.scenario_category == kind]
        assert part.ground_truth.eq("controlled_violation").any(), kind
        assert (
            part.loc[part.connection_activity == "normal", "ground_truth"]
            .ne("controlled_violation")
            .all()
        )
    outcomes["B_controlled"] = dict(
        status="passed",
        positive_connections=int(
            frame.loc[frame.ground_truth == "controlled_violation", "connection_id"].nunique()
        ),
        packet_attack_claim=False,
    )
    # Independent source remains fixed; misleading generator scenario cannot grant trust.
    copyroot = output / "changed-generator"
    original = next(p for p in captures.iterdir() if p.name.endswith("regular"))
    shutil.copytree(original, copyroot / original.name)
    p = copyroot / original.name / "ground-truth.json"
    t = json.loads(p.read_text())
    conn = t["connections"][0]
    target = conn["connection_id"]
    conn.update(activity="bad_credentials", auth_rejected=True, confirmed=True)
    t["experiment"]["scenario"] = "bad_credentials"
    p.write_text(json.dumps(t))
    changed = output / "changed-dataset"
    build(copyroot, changed)
    changed_rows = pd.read_csv(changed / "observations.csv", keep_default_na=False)
    assert (
        changed_rows.loc[changed_rows.connection_id == target, "ground_truth"].eq("unknown").all()
    )
    outcomes["C_forged_generator_evidence"] = dict(
        status="passed", target_activity="unknown", independent_broker_unchanged=True
    )
    # Actual broker DUP flags and receiver replay points, never a boolean printed by producer.
    qos = frame.loc[frame.scenario_category == "qos1_retry"]
    assert (
        not qos.empty
        and qos.ground_truth.ne("controlled_violation").all()
        and qos.ground_truth.eq("normal").any()
    )
    dup = 0
    for folder in captures.iterdir():
        t = json.loads((folder / "ground-truth.json").read_text())
        if t["experiment"]["scenario"] == "qos1_retry":
            dup += sum(
                e.get("dup") == 1
                for s in json.loads((folder / "broker-evidence.json").read_text())["sessions"]
                for e in s["events"]
            )
    assert dup >= 4
    outcomes["D_real_qos1_dup"] = dict(status="passed", broker_dup_events=dup, attack_rows=0)
    # Real artifact unavailability, not a mocked return value or stopped production broker.
    unavailable = output / "unavailable-evidence"
    shutil.copytree(original, unavailable / original.name)
    (unavailable / original.name / "broker-evidence.json").rename(
        unavailable / original.name / "broker-evidence-unavailable.json"
    )
    unout = output / "unavailable-dataset"
    build(unavailable, unout)
    assert pd.read_csv(unout / "observations.csv").ground_truth.eq("unknown").all()
    outcomes["E_missing_source"] = dict(
        status="passed",
        mechanism="independent journal unavailable on private capture copy; no service outage claimed",
        all_unknown=True,
    )
    # Stronger replay negative: independent ciphertext witness no longer matches generator.
    replay = next(p for p in captures.iterdir() if p.name.endswith("replay"))
    copyroot2 = output / "bad-digest"
    shutil.copytree(replay, copyroot2 / replay.name)
    p = copyroot2 / replay.name / "mqtt-observer.json"
    w = json.loads(p.read_text())
    for e in w["events"]:
        if e.get("payload_sha256"):
            e["payload_sha256"] = "f" * 64
    p.write_text(json.dumps(w))
    badout = output / "bad-digest-dataset"
    build(copyroot2, badout)
    assert pd.read_csv(badout / "observations.csv").ground_truth.ne("controlled_violation").all()
    outcomes["C_independent_digest_conflict"] = dict(
        status="passed", deliberate_replay_unverified=True
    )
    e_before = lab.state(time.time() - 30)
    missing_id = "gtfix-observer-" + output.name
    try:
        lab.experiment(
            Experiment(missing_id, "regular", 4, 6.0, 0.5, 0.01, 83001), evidence_fault_after=2
        )
    except RuntimeError as e:
        assert "evidence source unavailable" in str(e)
    else:
        raise AssertionError("Missing independent observer did not abort experiment")
    time.sleep(2)
    e_after = lab.state(time.time() - 30)
    assert (
        e_after["mongo_records"] > e_before["mongo_records"]
        and not (lab.output / missing_id).exists()
    )
    outcomes["E_live_observer_exit"] = dict(
        status="passed",
        source_process_terminated=True,
        experiment_aborted=True,
        mongo_delta=e_after["mongo_records"] - e_before["mongo_records"],
        no_verified_dataset=True,
    )
    before = lab.state(time.time() - 30)
    fault = "gtfix-collector-" + output.name
    try:
        lab.experiment(Experiment(fault, "regular", 4, 6.0, 0.5, 0.01, 83000), fault_after=2)
    except RuntimeError as e:
        assert "guard" in str(e)
    else:
        raise AssertionError("Collector fault did not terminate experiment")
    stopped = json.loads(
        lab.call(
            "exec",
            "-T",
            "lab-devices",
            "python",
            "-c",
            f"import json;from pathlib import Path;t=json.loads(Path('/research/{fault}/ground-truth.json').read_text());print(json.dumps({{'stopped':t['all_clients_stopped'],'duration':t['experiment_finished_at']-t['experiment_started_at']}}))",
        )
    )
    assert stopped["stopped"] and stopped["duration"] < 6 and not (lab.output / fault).exists()
    lab.call(
        "exec",
        "-T",
        "lab-devices",
        "python",
        "-c",
        "from pathlib import Path;r=Path('/proc/net/tcp').read_text().splitlines()[1:];assert not any(x.split()[3]=='01' and x.split()[2].endswith(':22B3') for x in r)",
    )
    time.sleep(2)
    after = lab.state(time.time() - 30)
    assert after["mongo_records"] > before["mongo_records"]
    outcomes["F_collector_fault"] = dict(
        status="passed",
        **stopped,
        mongo_delta=after["mongo_records"] - before["mongo_records"],
        unfinished_capture_in_dataset=False,
    )
    # Coherently rehashed derived labels must still fail against real raw sources.
    bad = output / "coherent-derived-tamper"
    shutil.copytree(data, bad)
    from src.research_stand.label_verification import table

    a = table(bad / "observations.csv")
    target = next(r for r in a if r["ground_truth"] == "normal")
    target.update(ground_truth="controlled_violation", attack_type="ControlledViolation", label="1")
    for name, rows in [
        ("observations.csv", a),
        ("dataset.csv", [r for r in a if r["ground_truth"] != "unknown"]),
    ]:
        with (bad / name).open("w") as f:
            writer = csv.DictWriter(f, fieldnames=list(a[0]))
            writer.writeheader()
            writer.writerows(rows)
    m = json.loads((bad / "dataset.manifest.json").read_text())
    m.update(
        sha256=digest(bad / "dataset.csv"), observations_sha256=digest(bad / "observations.csv")
    )
    (bad / "dataset.manifest.json").write_text(json.dumps(m))
    try:
        reconcile(bad, captures)
    except ValueError as e:
        assert "reconciliation mismatch: ground_truth" in str(e)
    else:
        raise AssertionError("Coherent derived tamper accepted")
    outcomes["coherent_real_csv_tamper"] = dict(status="rejected_logically", hashes_updated=True)
    assert source_before == {str(p): digest(p) for p in captures.rglob("*") if p.is_file()}
    result = dict(
        original_capture_hashes_unchanged=True,
        schema_version=1,
        project=lab.project,
        service=service,
        reconciliation=reconciliation,
        scenarios=outcomes,
        models_trained_on_lab_data=0,
        final_holdout_evaluated=False,
        label_accuracy=None,
    )
    (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--env-file", required=True)
    p.add_argument("--captures", required=True)
    p.add_argument("--output", required=True)
    a = p.parse_args()
    checks(a.env_file, a.captures, a.output)

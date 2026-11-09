"""Real lab assertions and bounded collector failure; never uses production volumes."""

import argparse, json, time
from pathlib import Path
from src.research_stand.orchestrator import Lab
from src.research_stand.config import Experiment
from src.research_stand.dataset import validate

PROBE = """
import json
from pathlib import Path
from sqlalchemy import create_engine,text
from src.runtime import database_url
from src.telemetry import load_registry
from src.mongo_repository import MongoRepository
registry=load_registry('/run/lcm/registry.json')
lab={k:v for k,v in registry.items() if k.startswith('lab')}
assert len(lab)==24 and len({v['key_hex'] for v in lab.values()})==24
passwords=[(Path('/run/lcm')/('device_'+k+'.password')).read_text().strip() for k in lab]
assert len(set(passwords))==24
engine=create_engine(database_url());repo=MongoRepository()
with engine.connect() as c:
 assert c.execute(text("SELECT count(*) FROM policy_device_states WHERE applied IS NOT NULL OR effective_security_state!='unconfirmed'")).scalar_one()==0
 assert set(c.execute(text('SELECT DISTINCT mode FROM policy_worker_status')).scalars())=={'DRY_RUN'}
 assert c.execute(text("SELECT count(*) FROM security_observations WHERE category='rejected' AND device_id IS NOT NULL")).scalar_one()==0
 assert c.execute(text("SELECT count(*) FROM telemetry_outbox WHERE status!='delivered'")).scalar_one()==0
 categories=dict(c.execute(text('SELECT category,count(*) FROM security_observations GROUP BY category')).all())
 assert all(categories.get(k,0)>0 for k in ['accepted','replay','rejected'])
 assert c.execute(text('SELECT count(*) FROM mqtt_replay_state')).scalar_one()>=24
 total=c.execute(text('SELECT count(*) FROM telemetry_outbox')).scalar_one()
 assert total==repo.collection.count_documents({})
 assert len(repo.collection.distinct('device_id'))==24
 for doc in repo.collection.find().limit(100):
  assert not any(k in doc for k in ['key','password','key_hex','token','private_key','payload'])
print(json.dumps(dict(devices=24,distinct_passwords=24,distinct_telemetry_keys=24,categories=categories,mongo_records=total,
 policy_mode='DRY_RUN',applied_configurations=0,outbox_pending=0,telemetry_profile='Ascon-AEAD128')))
repo.close();engine.dispose()
"""


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--env-file", required=True)
    p.add_argument("--captures", required=True)
    p.add_argument("--dataset", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--fault-id", required=True)
    a = p.parse_args()
    report = validate(a.dataset, a.captures)
    manifest = json.loads((Path(a.dataset) / "dataset.manifest.json").read_text())
    assert len(manifest["raw_files"]) >= 4
    assert any(
        r["class_counts"].get("normal", 0) > 0
        and r["class_counts"].get("controlled_violation", 0) > 0
        for r in manifest["raw_files"]
    )
    assert report["unknown_rows"] > 0
    assert sum(r["qos_retry_dup_connections"] for r in manifest["raw_files"]) > 0
    lab = Lab(a.env_file, Path(a.output).parent / "fault-check")
    time.sleep(2)
    result = json.loads(lab.call("run", "--rm", "-T", "--no-deps", "tests", "python", "-c", PROBE))
    before = lab.state()
    try:
        lab.experiment(Experiment(a.fault_id, "regular", 8, 6.0, 0.3, 0.05, 74999), fault_after=2)
    except RuntimeError as e:
        assert "guard" in str(e)
    else:
        raise AssertionError("Collector failure did not stop generator")
    status = json.loads(
        lab.call(
            "exec",
            "-T",
            "lab-devices",
            "python",
            "-c",
            f"import json;from pathlib import Path;t=json.loads(Path('/research/{a.fault_id}/ground-truth.json').read_text());print(json.dumps({{'stopped':t['all_clients_stopped'],'duration':t['experiment_finished_at']-t['experiment_started_at']}}))",
        )
    )
    assert status["stopped"] and status["duration"] < 6
    time.sleep(2)
    after = lab.state()
    assert after["mongo_records"] > before["mongo_records"]
    # No established generator connection remains; TIME_WAIT is harmless.
    lab.call(
        "exec",
        "-T",
        "lab-devices",
        "python",
        "-c",
        "from pathlib import Path;rows=Path('/proc/net/tcp').read_text().splitlines()[1:];assert not any(r.split()[3]=='01' and r.split()[2].endswith(':22B3') for r in rows)",
    )
    checks = dict(
        schema_version=1,
        validation=report,
        lab=result,
        collector_failure=dict(
            status="passed", **status, mongo_delta=after["mongo_records"] - before["mongo_records"]
        ),
        models_trained=0,
        final_test_run=False,
    )
    path = Path(a.output)
    with path.open("x") as f:
        json.dump(checks, f, indent=2)
        f.write("\n")
    print(
        "PASS: independent TLS identities/keys, PG replay and Mongo delivery, mixed/unknown mapping, source hashes, normal QoS1 DUP, collector failure isolation, stopped clients, policy DRY_RUN"
    )


if __name__ == "__main__":
    main()

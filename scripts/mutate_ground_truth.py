"""Small code mutations in temporary SOURCE copies; working branch never modified.
Only synthetic tests here. Real capture tampering is in the integration probe.
"""

import argparse, json, os, shutil, subprocess, tempfile
from pathlib import Path

MUTATIONS = [
    (
        "ignore_broker_auth_code",
        "src/research_stand/labels_v2.py",
        's["auth_code"] == 5 and record.get("auth_rejected")',
        'record.get("auth_rejected")',
        "test_generator_flag_cannot_replace_broker_result",
    ),
    (
        "drop_broker_outcome",
        "src/research_stand/labels_v2.py",
        "if s is None:",
        "if False:",
        "test_absent_broker_source_makes_every_connection_unknown",
    ),
    (
        "allow_without_SYN",
        "src/research_stand/labels_v2.py",
        "if syn and len(matches) == 1:",
        "if len(matches) == 1:",
        "test_no_syn_pipeline_cannot_attribute",
    ),
    (
        "unknown_to_normal",
        "src/research_stand/labels_v2.py",
        'label = "unknown"',
        'label = "normal"',
        "test_no_syn_pipeline_cannot_attribute",
    ),
    (
        "capture_wide_label",
        "src/research_stand/labels_v2.py",
        "output.append(",
        """if truth['experiment']['scenario']=='bad_credentials':label='controlled_violation'
        output.append(""",
        "test_public_pipeline_positive_mixed_and_unknown",
    ),
    (
        "skip_source_identity",
        "src/research_stand/label_verification.py",
        "if actual.get(field) != str(value):",
        "if False:",
        "test_coherent_hash_tampering_is_rejected[connection]",
    ),
    (
        "wrong_stream_binding",
        "src/research_stand/labels_v2.py",
        "assigned[key] = matches[0]",
        'assigned[key] = truth["connections"][0]',
        "test_public_pipeline_positive_mixed_and_unknown",
    ),
    (
        "scenario_name_is_proof",
        "src/research_stand/labels_v2.py",
        "if len(points) >= 8 and baseline:",
        "if True:",
        "test_unverified_behavior_never_positive_through_public_pipeline",
    ),
]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True)
    a = p.parse_args()
    root = Path.cwd()
    results = []
    preflight = subprocess.run(
        [
            str(root / ".venv/bin/python"),
            "-m",
            "pytest",
            "-q",
            "--noconftest",
            "tests/test_ground_truth_hardening.py",
        ],
        capture_output=True,
        text=True,
        timeout=45,
    )
    if preflight.returncode:
        raise RuntimeError(
            "Unmutated baseline must pass before any mutation: " + preflight.stdout[-1000:]
        )
    for name, file, before, after, test in MUTATIONS:
        with tempfile.TemporaryDirectory(prefix="lcm-mutation-") as tmp:
            tmp = Path(tmp)
            shutil.copytree(
                root / "src",
                tmp / "src",
                ignore=shutil.ignore_patterns(
                    "__pycache__", "Edge-IIoTset dataset", "*.ipynb", "*.zip"
                ),
            )
            (tmp / "tests").mkdir()
            shutil.copyfile(
                root / "tests/test_ground_truth_hardening.py",
                tmp / "tests/test_ground_truth_hardening.py",
            )
            path = tmp / file
            s = path.read_text()
            if before not in s:
                raise ValueError("Stale mutation selector: " + name)
            path.write_text(s.replace(before, after, 1))
            command = [
                str(root / ".venv/bin/python"),
                "-m",
                "pytest",
                "-q",
                "--noconftest",
                f"tests/test_ground_truth_hardening.py::{test}",
            ]
            env = {**os.environ, "PYTHONPATH": str(tmp), "PYTHONDONTWRITEBYTECODE": "1"}
            run = subprocess.run(
                command,
                cwd=tmp,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=45,
            )
            # Syntax/import errors do not count as killed behavioral mutants.
            killed = (
                run.returncode == 1
                and "FAILED" in run.stdout
                and "ERROR collecting" not in run.stdout
                and "SyntaxError" not in run.stdout
            )
            results.append(
                dict(
                    injected_defect=name,
                    test=test,
                    expected="pytest behavior assertion/reconciliation failure",
                    exit_code=run.returncode,
                    observed="killed_by_behavior" if killed else "SURVIVED_OR_INVALID",
                    output_tail=run.stdout[-1800:],
                )
            )
    Path(a.output).write_text(
        json.dumps(
            dict(
                schema_version=1,
                baseline_exit_code=preflight.returncode,
                baseline_output=preflight.stdout.strip(),
                scope="temporary source copies; synthetic protocol fixtures; no ML fitting",
                results=results,
                all_killed=all(x["observed"] == "killed_by_behavior" for x in results),
            ),
            indent=2,
        )
        + "\n"
    )
    print(json.dumps({x["injected_defect"]: x["observed"] for x in results}, indent=2))
    if not all(x["observed"] == "killed_by_behavior" for x in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

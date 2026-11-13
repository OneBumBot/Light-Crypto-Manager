"""Opt-in isolated lab orchestrator. No external targets, no model training."""

import argparse, json, os, re, shutil, subprocess, time, uuid
from pathlib import Path
import signal
from .config import Experiment, NORMAL, VIOLATIONS


class Lab:
    def __init__(self, env, output, *, compose_overrides=()):
        self.output = Path(output).resolve()
        self.output.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.cmd = [
            "docker",
            "compose",
            "--env-file",
            str(env),
            "-f",
            "compose.yaml",
            "-f",
            "compose.research.yaml",
            "--profile",
            "research",
        ]
        if compose_overrides:
            self.cmd = self.cmd[:-2] + sum([['-f', str(Path(f).resolve())] for f in compose_overrides], []) + self.cmd[-2:]
        cfg = json.loads(
            subprocess.check_output(
                self.cmd + ["--profile", "*", "config", "--format", "json"], text=True
            )
        )
        self.project = cfg["name"]
        if not (self.project.startswith("lcm-stage7b-") or re.fullmatch(r"lcm-stage14-ground-truth-[a-z0-9-]{1,18}", self.project)):
            raise ValueError("Dedicated research project required")
        if cfg["networks"]["default"].get("internal") is not True:
            raise ValueError("Internal network mandatory")
        for name in ["broker", "web", "mongo", "postgres"]:
            if cfg["services"][name].get("ports"):
                raise ValueError("Lab must not expose host ports")
        for name in ["lab-devices", "traffic-collector", "broker", "receiver", "postgres", "mongo"]:
            service = cfg["services"][name]
            if not service.get("mem_limit") or not service.get("cpus"):
                raise ValueError("CPU/RAM limits required")
        # Inspect the actual namespace, not only the file used by this process.
        cid = self.call("ps", "-q", "lab-devices").strip()
        if not cid:
            raise ValueError("Start the lab first")
        info = json.loads(subprocess.check_output(["docker", "inspect", cid], text=True))[0]
        for network in info["NetworkSettings"]["Networks"]:
            n = json.loads(
                subprocess.check_output(["docker", "network", "inspect", network], text=True)
            )[0]
            if not n["Internal"] or n["Labels"].get("com.docker.compose.project") != self.project:
                raise ValueError("Unsafe actual network")
        self.collector = self.call("ps", "-q", "traffic-collector").strip()
        if not self.collector:
            raise ValueError("Collector service missing")

    def call(self, *args, timeout=90):
        result = subprocess.run(
            self.cmd + list(args), capture_output=True, text=True, timeout=timeout
        )
        if result.returncode:
            raise RuntimeError(
                "Compose operation failed: "
                + str(args[:3])
                + "; exit="
                + str(result.returncode)
                + "; inspect private logs"
            )
        return result.stdout

    def state(self, since=0):
        return json.loads(
            self.call(
                "run",
                "--rm",
                "-T",
                "--no-deps",
                "-e",
                f"RESEARCH_SINCE={since}",
                "tests",
                "python",
                "-m",
                "scripts.stand_state",
            )
        )

    def resource_usage(self):
        usage = {}
        for service, path in [
            ("postgres", "/var/lib/postgresql/data"),
            ("mongo", "/data/db"),
            ("lab-devices", "/research"),
        ]:
            value = int(self.call("exec", "-T", service, "du", "-sk", path).split()[0]) * 1024
            maximum = 512 * 1024**2 if service == "lab-devices" else 1024**3
            if value > maximum:
                raise ValueError("Research volume disk budget exceeded: " + service)
            usage[service] = dict(bytes=value, limit=maximum)
        return usage

    def experiment(self, cfg, *, fault_after=None, evidence_fault_after=None):
        cfg.validate()
        identity = cfg.experiment_id
        if (self.output / identity).exists():
            raise ValueError("Existing experiment preserved")
        if shutil.disk_usage(self.output).free < 2 * 1024**3:
            raise ValueError("Free disk floor2GiB")
        if sum(p.stat().st_size for p in self.output.rglob("*") if p.is_file()) > 512 * 1024**2:
            raise ValueError("Lab output budget512MiB")
        # Host load guard supplements hard container quotas; no sustained background overload.
        if os.getloadavg()[0] > max(4, (os.cpu_count() or 1) * 0.75):
            raise ValueError("Host load guard")
        before = self.state(time.time() - 30)
        usage = self.resource_usage()
        start = time.time()
        remote = "/research/" + identity
        self.call(
            "exec",
            "-T",
            "lab-devices",
            "python",
            "-c",
            "import pathlib; p=pathlib.Path('/research/configs');p.mkdir(exist_ok=True);(p/'"
            + identity
            + ".json').write_text("
            + repr(json.dumps(cfg.payload()))
            + ")",
        )
        proc = subprocess.Popen(
            self.cmd
            + [
                "exec",
                "-T",
                "traffic-collector",
                "python",
                "-m",
                "src.research_stand.collector",
                "capture",
                "--directory",
                remote,
                "--duration",
                str(cfg.duration + 8),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        witness = None
        try:
            witness = subprocess.Popen(
                self.cmd
                + [
                    "exec",
                    "-T",
                    "research-observer",
                    "python",
                    "-m",
                    "src.research_stand.observer",
                    "--directory",
                    remote,
                    "--duration",
                    str(min(30, cfg.duration + 12)),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            until = time.monotonic() + 5
            while time.monotonic() < until:
                if witness.poll() is not None:
                    raise RuntimeError("Independent observer unavailable")
                ready = self.call(
                    "exec",
                    "-T",
                    "lab-devices",
                    "python",
                    "-c",
                    f"from pathlib import Path;print(Path('{remote}/observer-ready').exists())",
                ).strip()
                if ready == "True":
                    break
                time.sleep(0.1)
            else:
                raise RuntimeError("Observer readiness timeout")
            until = time.monotonic() + 6
            while time.monotonic() < until:
                if proc.poll() is not None:
                    raise RuntimeError(
                        "Collector exited before readiness: " + proc.communicate()[1][-300:]
                    )
                ready = self.call(
                    "exec",
                    "-T",
                    "lab-devices",
                    "python",
                    "-c",
                    f"from pathlib import Path;print(Path('{remote}/capture-ready').exists())",
                ).strip()
                if ready == "True":
                    break
                time.sleep(0.1)
            else:
                raise RuntimeError("Collector readiness timeout")
            driver = subprocess.Popen(
                self.cmd
                + [
                    "exec",
                    "-T",
                    "lab-devices",
                    "python",
                    "-m",
                    "src.research_stand.driver",
                    "--config",
                    "/research/configs/" + identity + ".json",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            deadline = time.monotonic() + cfg.duration + 12
            evidence_fault_time = (
                time.monotonic() + evidence_fault_after if evidence_fault_after else None
            )
            last_guard = 0
            fault_time = time.monotonic() + fault_after if fault_after else None
            try:
                while driver.poll() is None:
                    if evidence_fault_time and time.monotonic() > evidence_fault_time:
                        self.call(
                            "exec",
                            "-T",
                            "research-observer",
                            "python",
                            "-c",
                            f"import os,signal;from pathlib import Path;p=int(Path('{remote}/observer.pid').read_text());assert p>1;os.kill(p,signal.SIGTERM)",
                        )
                        evidence_fault_time = None
                    if witness.poll() is not None:
                        raise RuntimeError(
                            "Independent evidence source unavailable; stopping experiment"
                        )
                    if fault_time and time.monotonic() > fault_time:
                        self.call(
                            "exec",
                            "-T",
                            "lab-devices",
                            "python",
                            "-c",
                            f"from pathlib import Path;Path('{remote}/stop-capture').touch()",
                        )
                        fault_time = None
                    if time.monotonic() - last_guard > 2:
                        self.resource_usage()
                        last_guard = time.monotonic()
                        if os.getloadavg()[0] > max(4, (os.cpu_count() or 1) * 0.75):
                            raise RuntimeError("Host load guard")
                    if (
                        proc.poll() is not None
                        or time.monotonic() > deadline
                        or shutil.disk_usage(self.output).free < 1024**3
                    ):
                        raise RuntimeError(
                            "Experiment resource or collector guard; stopping clients"
                        )
                    time.sleep(0.1)
                out, err = driver.communicate()
                if driver.returncode:
                    raise RuntimeError("Generator failed; experiment quarantined")
                print(out.strip(), flush=True)
            finally:
                if driver.poll() is None:
                    self.call(
                        "exec",
                        "-T",
                        "lab-devices",
                        "python",
                        "-c",
                        f"import os,signal;from pathlib import Path;p=int(Path('{remote}/driver.pid').read_text());assert p>1;os.kill(p,signal.SIGTERM)",
                    )
                    driver.communicate(timeout=10)
        finally:
            self.call(
                "exec",
                "-T",
                "lab-devices",
                "python",
                "-c",
                f"from pathlib import Path;[(Path('{remote}')/name).touch() for name in ['stop-observer','stop-capture']]",
            )
            try:
                if witness is not None:
                    witness.communicate(timeout=10)
            finally:
                out, err = proc.communicate(timeout=10)
            if proc.returncode:
                raise RuntimeError("Collector failed during cleanup")
            if witness is not None and witness.returncode:
                raise RuntimeError("Independent observer failed")
        self.call(
            "exec",
            "-T",
            "traffic-collector",
            "python",
            "-m",
            "src.research_stand.collector",
            "extract",
            "--directory",
            remote,
        )
        # Never persist raw broker logs; allowlist only opaque client IDs and event counts.
        log = self.call("logs", "--no-log-prefix", "--since", str(int(start)), "broker")
        denied = re.findall(r"Denied PUBLISH from (lab-[0-9a-f]+)", log)
        broker_events = dict(
            acl_denied_clients=sorted(set(denied)),
            authentication_rejections=log.count("not authorised"),
            source="isolated Mosquitto log allowlist",
        )
        from .broker_evidence import parse

        independent_log = self.call(
            "logs", "--timestamps", "--no-log-prefix", "--since", str(int(start)), "broker"
        )
        broker_evidence = parse(independent_log, start, time.time())
        time.sleep(0.5)
        after = self.state(start)
        core = {
            **after,
            "resource_usage": usage,
            "before": before,
            "rejected_delta": after["categories"].get("rejected", 0)
            - before["categories"].get("rejected", 0),
            "mongo_delta": after["mongo_records"] - before["mongo_records"],
        }
        subprocess.run(
            ["docker", "cp", self.collector + ":" + remote, str(self.output / identity)],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        folder = self.output / identity
        for p in [folder, *folder.rglob("*")]:
            if p.is_symlink():
                raise ValueError("Symlink forbidden in capture")
            p.chmod(0o700 if p.is_dir() else 0o600)
        (folder / "broker-events.json").write_text(json.dumps(broker_events, indent=2) + "\n")
        (folder / "broker-evidence.json").write_text(json.dumps(broker_evidence, indent=2) + "\n")
        (folder / "core.json").write_text(json.dumps(core, indent=2) + "\n")
        for p in folder.iterdir():
            p.chmod(0o600)
        return identity


def matrix(size, prefix):
    if size not in (4, 60):
        raise ValueError("Only pilot4 or primary60 matrix")
    result = []
    for i in range(size // 2):
        seed = 75000 + i
        clients = 8 if size == 4 else [8, 12, 16, 20][i % 4]
        for violation in [False, True]:
            scenario = (VIOLATIONS if violation else NORMAL)[
                (i + 2 if size == 4 and violation else i) % 6
            ]
            result.append(
                Experiment(
                    f"{prefix}-{i:02d}-" + ("v" if violation else "n"),
                    scenario,
                    clients,
                    6.0,
                    [0.3, 0.5, 0.7][i % 3],
                    0.08,
                    seed,
                    violation,
                )
            )
    return result


def main():
    def shutdown(*_):
        raise KeyboardInterrupt("Research experiment stop requested")

    signal.signal(signal.SIGTERM, shutdown)
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--env-file", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--matrix", choices=["pilot", "primary"], required=True)
    p.add_argument("--prefix", required=True)
    a = p.parse_args()
    lab = Lab(a.env_file, a.output)
    for config in matrix(4 if a.matrix == "pilot" else 60, a.prefix):
        lab.experiment(config)


if __name__ == "__main__":
    main()

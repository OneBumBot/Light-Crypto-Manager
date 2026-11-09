"""Create fresh private configuration for an isolated lab; never reuse production secrets."""

import argparse, subprocess, os, re
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--directory", type=Path, required=True)
    p.add_argument("--project", required=True)
    a = p.parse_args()
    if not re.fullmatch(r"lcm-stage7b-[a-z0-9-]{1,25}", a.project):
        p.error("Dedicated lcm-stage7b-* project required")
    os.umask(0o077)
    root = a.directory.resolve()
    root.mkdir(parents=True, exist_ok=False, mode=0o700)
    env = root / "compose.env"
    subprocess.run(
        [
            "python3",
            "scripts/prepare_compose.py",
            "--env-file",
            str(env),
            "--project",
            a.project,
            "--mqtt-port",
            "0",
            "--web-port",
            "0",
        ],
        check=True,
    )
    subprocess.run(
        ["python3", "scripts/prepare_security.py", "--directory", str(root / "mqtt")]
        + sum([["--extra-device", f"lab{i:03}"] for i in range(1, 25)], []),
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    subprocess.run(
        ["python3", "scripts/prepare_storage.py", "--directory", str(root / "mongo")], check=True
    )
    s = (
        env.read_text()
        .replace(
            "MQTT_SECURITY_DIR=.local-runtime/security", "MQTT_SECURITY_DIR=" + str(root / "mqtt")
        )
        .replace(
            "MONGO_SECURITY_DIR=.local-runtime/mongo-security",
            "MONGO_SECURITY_DIR=" + str(root / "mongo"),
        )
    )
    env.write_text(s)
    print("Isolated configuration ready. No services started; values withheld.")


if __name__ == "__main__":
    main()

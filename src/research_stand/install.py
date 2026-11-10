"""Provision scoped device credentials/state volume; no receiver/control passwords."""

import json, os, shutil
from pathlib import Path


def invalid_password(length):
    if type(length) is not int or not 16 <= length <= 128:
        raise ValueError("Unexpected test credential length")
    # Non-hex public fixture is distinct from generated hex credentials, with equal length.
    return "invalid-lab".ljust(length, "x")


def main():
    source = Path("/input")
    out = Path("/out/credentials")
    out.mkdir(exist_ok=True)
    registry = json.loads((source / "registry.json").read_text())
    selected = {k: v for k, v in registry.items() if k.startswith("lab")}
    if not 2 <= len(selected) <= 24:
        raise ValueError("Expected lab device pool2..24")
    for name, entry in selected.items():
        path = out / name
        path.mkdir(exist_ok=True)
        shutil.copyfile(source / "ca.crt", path / "ca.crt")
        shutil.copyfile(source / ("device_" + name + ".password"), path / "mqtt.password")
        (path / "registry.json").write_text(json.dumps({name: entry}))
    (out / "bad.password").write_text(invalid_password(48) + "\n")
    for root in [out, Path("/out/state"), Path("/out/data")]:
        root.mkdir(exist_ok=True)
        for path in [root, *root.rglob("*")]:
            path.chmod(0o700 if path.is_dir() else 0o600)
            os.chown(path, 10001, 10001)
    print("Scoped laboratory device pool installed; values withheld")


if __name__ == "__main__":
    main()

"""Preview deletion of explicitly named old completed private captures; no default purge."""

import argparse, json, re, shutil, time
from pathlib import Path
from .collector import sha


def eligible(root, identity, days, now=None):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,60}", identity):
        raise ValueError("Explicit capture identity required")
    root = Path(root).resolve()
    folder = root / identity
    if folder.is_symlink() or folder.resolve().parent != root:
        raise ValueError("Unsafe capture path")
    if type(days) is not int or days < 1:
        raise ValueError("Retention at least1day")
    for path in folder.rglob("*"):
        if path.is_symlink():
            raise ValueError("Symlink in capture")
    capture = json.loads((folder / "capture.json").read_text())
    truth = json.loads((folder / "ground-truth.json").read_text())
    if truth["experiment"]["experiment_id"] != identity or capture["pcap_sha256"] != sha(
        folder / "traffic.pcap"
    ):
        raise ValueError("Incomplete or modified capture")
    return (now or time.time()) - truth["experiment_finished_at"] >= days * 86400


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", required=True)
    p.add_argument("--capture", action="append", required=True)
    p.add_argument("--older-than-days", type=int, default=30)
    p.add_argument("--apply", action="store_true")
    a = p.parse_args()
    for identity in a.capture:
        if eligible(a.root, identity, a.older_than_days):
            print(("DELETE" if a.apply else "PREVIEW") + " " + identity)
            if a.apply:
                shutil.rmtree(Path(a.root).resolve() / identity)
        else:
            print("KEEP recent " + identity)


if __name__ == "__main__":
    main()

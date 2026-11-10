"""Capture only generator namespace traffic to its internal broker. Offline extractor allowlist."""

import argparse, csv, hashlib, json, os, re, signal, socket, subprocess, time, shutil, resource
from pathlib import Path

FIELDS = [
    "frame.number",
    "frame.time_epoch",
    "frame.len",
    "ip.src",
    "ip.dst",
    "tcp.srcport",
    "tcp.dstport",
    "tcp.stream",
    "tcp.len",
    "tcp.flags",
    "tcp.window_size_value",
    "tcp.time_delta",
    "ip.proto",
    "tcp.analysis.lost_segment",
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def capture(directory, duration):
    if not 3 <= duration <= 30:
        raise ValueError("Bounded capture duration required")
    os.umask(0o077)
    directory.mkdir(exist_ok=True, mode=0o700)
    pcap = directory / "traffic.pcap"
    if pcap.exists():
        raise ValueError("Capture immutable")
    if shutil.disk_usage(directory).free < 1024**3:
        raise ValueError("Minimum free disk1GiB required")
    broker = socket.gethostbyname("broker")
    cmd = [
        "tcpdump",
        "-p",
        "-i",
        "eth0",
        "-U",
        "-s",
        "0",
        "-B",
        "4096",
        "-c",
        "20000",
        "-w",
        str(pcap),
        "tcp and host " + broker + " and port 8883",
    ]
    process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    stop = False

    def shutdown(*_):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    started = time.time()
    reason = "duration"
    try:
        deadline = time.monotonic() + duration
        while time.monotonic() < deadline and not stop:
            if process.poll() is not None:
                reason = "process_exit"
                break
            if pcap.exists() and pcap.stat().st_size > 0:
                (directory / "capture-ready").touch()
            if pcap.exists() and pcap.stat().st_size > 8 * 1024 * 1024:
                reason = "size_limit"
                break
            if shutil.disk_usage(directory).free < 512 * 1024**2:
                reason = "disk_limit"
                break
            if (directory / "stop-capture").exists():
                reason = "orchestrator_stop"
                break
            time.sleep(0.05)
    finally:
        if process.poll() is None:
            process.send_signal(signal.SIGINT)
        _, output = process.communicate(timeout=5)
        (directory / "capture-ready").unlink(missing_ok=True)
    values = {}
    for label, key in [
        ("packets captured", "captured"),
        ("packets received by filter", "received_by_filter"),
        ("packets dropped by kernel", "dropped_by_kernel"),
    ]:
        match = re.search(r"(\d+) " + label, output)
        values[key] = int(match.group(1)) if match else None
    if not pcap.exists() or process.returncode not in [0]:
        raise RuntimeError("Collector failed; " + output[-200:])
    header = pcap.read_bytes()[:24]
    link = int.from_bytes(header[20:24], "little")
    manifest = dict(
        schema_version=1,
        pcap_sha256=sha(pcap),
        bytes=pcap.stat().st_size,
        started_at=started,
        finished_at=time.time(),
        capture_point="lab-devices eth0, original publisher -> broker connections",
        interface="eth0",
        link_layer_type=link,
        filter="tcp and host INTERNAL_BROKER and port8883",
        stats=values,
        stop_reason=reason,
        tcpdump_version=subprocess.check_output(["tcpdump", "--version"], text=True).splitlines()[
            0
        ],
        collector_peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    )
    (directory / "capture.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("Bounded private TLS capture completed")


def extract(directory):
    os.umask(0o077)
    pcap = directory / "traffic.pcap"
    output = directory / "headers.csv"
    if output.exists():
        raise ValueError("Header export immutable")
    cmd = [
        "tshark",
        "-r",
        str(pcap),
        "-n",
        "-Y",
        "tcp",
        "-T",
        "fields",
        "-E",
        "header=y",
        "-E",
        "separator=,",
        "-E",
        "quote=d",
        "-E",
        "occurrence=f",
    ]
    for field in FIELDS:
        cmd += ["-e", field]
    with output.open("x") as stream:
        subprocess.run(
            cmd, stdout=stream, stderr=subprocess.PIPE, text=True, check=True, timeout=30
        )
    meta = dict(
        schema_version=1,
        extractor_version="lcm-tshark-tcp-v1",
        feature_version="tcp-packet-passive-v1",
        pcap_sha256=sha(pcap),
        csv_sha256=sha(output),
        tool_version=subprocess.check_output(["tshark", "--version"], text=True).splitlines()[0],
        fields=FIELDS,
        interpretation="Only numeric headers and provenance; TLS never decrypted",
    )
    (directory / "extractor.json").write_text(json.dumps(meta, indent=2) + "\n")
    print("Offline TCP header export completed")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=["capture", "extract"])
    p.add_argument("--directory", type=Path, required=True)
    p.add_argument("--duration", type=float, default=15)
    a = p.parse_args()
    capture(a.directory, a.duration) if a.command == "capture" else extract(a.directory)

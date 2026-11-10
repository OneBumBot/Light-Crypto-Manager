"""Bounded independent PCAP identity oracle. Only classic PCAP/Ethernet/IPv4/TCP.
Unsupported/truncated/fragmented formats fail closed; never decodes TLS/MQTT.
Format: libpcap pcap-savefile(5). No whole-PCAP read into RAM.
"""

import csv, hashlib, ipaddress, math, struct
from itertools import islice
from pathlib import Path


def digest(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def load_json(path):
    import json

    path = Path(path)
    if path.is_symlink() or path.stat().st_size > 8 * 1024**2:
        raise ValueError("Evidence file resource/path bound")
    return json.loads(path.read_text())


def headers(folder):
    folder = Path(folder)
    cap = load_json(folder / "capture.json")
    ext = load_json(folder / "extractor.json")
    if (
        digest(folder / "traffic.pcap") != cap["pcap_sha256"]
        or ext["pcap_sha256"] != cap["pcap_sha256"]
        or digest(folder / "headers.csv") != ext["csv_sha256"]
    ):
        raise ValueError("Source capture/header hash mismatch")
    if cap["stats"]["dropped_by_kernel"] != 0 or cap["stop_reason"] not in [
        "duration",
        "orchestrator_stop",
    ]:
        raise ValueError("Incomplete/lost capture")
    if (folder / "traffic.pcap").stat().st_size > 16 * 1024**2 or (
        folder / "headers.csv"
    ).stat().st_size > 16 * 1024**2:
        raise ValueError("Capture resource bound")
    with (folder / "headers.csv").open() as f:
        rows = list(islice(csv.DictReader(f), 20001))
    if not rows or len(rows) > 20000 or len(rows) != cap["stats"]["captured"]:
        raise ValueError("Physical packet count mismatch")
    raw = list(packets(folder / "traffic.pcap"))
    if len(raw) != len(rows):
        raise ValueError("PCAP/header count mismatch")
    stream_for_wire = {}
    initial_sequence = {}
    stream_count = 0
    seen = set()
    stream_wires = {}
    last = {}
    for row, packet in zip(rows, raw):
        number = str(packet["number"])
        wire = packet["wire"]
        key = tuple(sorted([wire[:2], wire[2:]]))
        if row["frame.number"] != number or number in seen:
            raise ValueError("PCAP packet identity mismatch")
        seen.add(number)
        if (row["ip.src"], row["tcp.srcport"], row["ip.dst"], row["tcp.dstport"]) != wire:
            raise ValueError("PCAP socket tuple mismatch")
        epoch = float(row["frame.time_epoch"])
        if not math.isfinite(epoch) or abs(epoch - packet["time"]) > 1.1e-6:
            raise ValueError("PCAP timestamp mismatch")
        checks = {
            "frame.len": packet["length"],
            "tcp.len": packet["payload_length"],
            "tcp.flags": packet["flags"],
            "tcp.window_size_value": packet["window"],
        }
        for field, value in checks.items():
            parsed = int(row[field], 0) if field == "tcp.flags" else float(row[field])
            if parsed != value:
                raise ValueError("PCAP feature mismatch: " + field)
        numeric_delta = float(row["tcp.time_delta"])
        if (
            not math.isfinite(numeric_delta)
            or not 0 <= numeric_delta <= 86400
            or packet["flags"] > 511
        ):
            raise ValueError("Unsupported passive-v1 feature range")
        delta = packet["time"] - last.get(key, packet["time"])
        last[key] = packet["time"]
        if abs(float(row["tcp.time_delta"]) - delta) > 1.1e-6:
            raise ValueError("PCAP TCP delta mismatch")
        if key not in stream_for_wire or (
            packet["flags"] & 2
            and not packet["flags"] & 16
            and key in initial_sequence
            and initial_sequence[key] != packet["sequence"]
        ):
            stream_for_wire[key] = str(stream_count)
            stream_count += 1
        if packet["flags"] & 2 and not packet["flags"] & 16:
            initial_sequence[key] = packet["sequence"]
        if row["tcp.stream"] != stream_for_wire[key]:
            raise ValueError("PCAP stream identity mismatch")
        stream = row["tcp.stream"]
        if stream in stream_wires and stream_wires[stream] != key:
            raise ValueError("Mixed wire tuple in stream")
        stream_wires[stream] = key
    return rows, cap, ext


def packets(path):
    magic = {
        b"\xd4\xc3\xb2\xa1": ("<", 1e6),
        b"\xa1\xb2\xc3\xd4": (">", 1e6),
        b"\x4d\x3c\xb2\xa1": ("<", 1e9),
        b"\xa1\xb2\x3c\x4d": (">", 1e9),
    }
    with Path(path).open("rb") as f:
        header = f.read(24)
        if len(header) != 24 or header[:4] not in magic:
            raise ValueError("Unsupported PCAP format")
        endian, scale = magic[header[:4]]
        major, minor, _, _, snap, link = struct.unpack(endian + "HHIIII", header[4:])
        if (major, minor) != (2, 4) or link != 1 or not 54 <= snap <= 1048576:
            raise ValueError("Unsupported PCAP link/version")
        for number in range(1, 20002):
            record = f.read(16)
            if not record:
                return
            if len(record) != 16 or number > 20000:
                raise ValueError("PCAP record/resource bound")
            sec, frac, included, original = struct.unpack(endian + "IIII", record)
            if not 54 <= included <= min(snap, 65535) or included != original or frac >= scale:
                raise ValueError("Truncated/oversized PCAP packet")
            frame = f.read(included)
            if len(frame) != included or frame[12:14] != b"\x08\x00":
                raise ValueError("Unsupported Ethernet frame")
            ip = frame[14:]
            ihl = (ip[0] & 15) * 4
            if (
                ip[0] >> 4 != 4
                or ihl < 20
                or ip[9] != 6
                or (int.from_bytes(ip[6:8], "big") & 0x3FFF)
            ):
                raise ValueError("Unsupported IP/fragment protocol")
            length = int.from_bytes(ip[2:4], "big")
            tcp = ip[ihl:]
            offset = (tcp[12] >> 4) * 4
            if offset < 20 or length > len(ip) or length < ihl + offset:
                raise ValueError("Invalid TCP header")
            src, dst = struct.unpack("!HH", tcp[:4])
            flags = ((tcp[12] & 15) << 8) | tcp[13]
            yield dict(
                sequence=int.from_bytes(tcp[4:8], "big"),
                number=number,
                time=sec + frac / scale,
                length=original,
                payload_length=length - ihl - offset,
                flags=flags,
                window=int.from_bytes(tcp[14:16], "big"),
                wire=(
                    str(ipaddress.IPv4Address(ip[12:16])),
                    str(src),
                    str(ipaddress.IPv4Address(ip[16:20])),
                    str(dst),
                ),
            )

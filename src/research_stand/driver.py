"""Bounded virtual devices; target fixed to this isolated Compose broker, TLS mandatory."""

import argparse, base64, hashlib, ipaddress, json, os, random, signal, socket, time, uuid, resource
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Event, Lock
import paho.mqtt.client as mqtt
from src.mqtt_transport import configure_client
from src.sequence import next_sequence
from src.telemetry import load_registry, encode_packet, decode_packet, InvalidTelemetry
from .config import Experiment


def run(config, root):
    config.validate()
    os.umask(0o077)
    if os.environ.get("MQTT_INSECURE_TEST_MODE"):
        raise ValueError("Insecure mode forbidden in collection")
    broker = socket.gethostbyname("broker")
    if not ipaddress.ip_address(broker).is_private or ipaddress.ip_address(broker).is_loopback:
        raise ValueError("Internal broker only")
    directory = Path(root) / config.experiment_id
    directory.mkdir(mode=0o700, exist_ok=True)
    if (directory / "ground-truth.json").exists():
        raise ValueError("Experiment immutable")
    stop = Event()
    lock = Lock()
    rate_lock = Lock()
    next_send = [0.0]
    records = []
    errors = []
    messages = []
    (directory / "driver.pid").write_text(str(os.getpid()))
    for sig in [signal.SIGINT, signal.SIGTERM]:
        signal.signal(sig, lambda *_: stop.set())
    pool = sorted(
        p.name for p in Path("/run/research").iterdir() if p.is_dir() and p.name.startswith("lab")
    )
    rng = random.Random(config.seed)
    rng.shuffle(pool)
    selected = pool[: config.clients]
    if len(selected) != config.clients:
        raise ValueError("Not enough independently provisioned devices")
    actor_index = config.seed % config.clients
    started = time.time()
    mono = time.monotonic()
    deadline = mono + config.duration

    def worker(index, name):
        local = random.Random(config.seed * 100 + index)
        folder = Path("/run/research") / name
        registry = load_registry(folder / "registry.json")
        entry = registry[name]
        actor = config.violation and index == actor_index
        packet = None
        packet_sequence = None
        count = 0
        retry_dup = 0
        stop.wait(index * 0.09)  # bounded startup connection rate <=12/s

        def make_packet():
            seq = next_sequence("/state/sequence.db", name, entry["key_epoch"])
            sensor = dict(
                temperature=22 + local.random() * 2,
                humidity=45 + local.random() * 3,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
            return encode_packet(sensor, registry, name, seq), seq

        def connection(kind):
            ready = Event()
            client_id = "lab-" + uuid.uuid4().hex
            record = dict(
                connection_id=str(uuid.uuid4()),
                client_id=client_id,
                actor_slot=index,
                process_id=os.getpid(),
                logical_device=name,
                activity=kind,
                attempt_started_at=time.time(),
                tls_open_at=None,
                closed_at=None,
                authenticated=False,
                auth_rejected=False,
                confirmed=False,
                normal_retry_dup_observed=False,
                actions=[],
            )
            client = mqtt.Client(
                mqtt.CallbackAPIVersion.VERSION2, client_id=client_id, clean_session=False
            )

            def opened(c, u, s):
                nonlocal record
                if record["tls_open_at"] is not None:
                    previous = record
                    record = {
                        **previous,
                        "connection_id": str(uuid.uuid4()),
                        "tls_open_at": None,
                        "closed_at": None,
                        "actions": [],
                        "confirmed": False,
                        "authenticated": False,
                        "normal_retry_dup_observed": False,
                    }
                with lock:
                    records.append(record)
                record.update(
                    tls_open_at=time.time(),
                    local_ip=s.getsockname()[0],
                    local_port=s.getsockname()[1],
                    remote_ip=s.getpeername()[0],
                    remote_port=s.getpeername()[1],
                )

            def closed(c, u, s):
                record["closed_at"] = time.time()

            def connected(c, u, f, reason, p):
                record["authenticated"] = reason == 0
                record["auth_rejected"] = reason != 0
                ready.set()

            def log(c, u, level, buf):
                if "Sending PUBLISH (d1, q1" in buf:
                    record["normal_retry_dup_observed"] = True

            client.on_socket_open = opened
            client.on_socket_close = closed
            client.on_connect = connected
            client.on_log = log
            password = (
                "/run/research/bad.password"
                if kind == "bad_credentials"
                else str(folder / "mqtt.password")
            )
            configure_client(
                client,
                username="device_" + name,
                password_file=password,
                ca_file=str(folder / "ca.crt"),
            )
            client.connect("broker", 8883, 30)
            # Synchronous network loop makes uncertain-ACK reconnect controllable.
            until = time.monotonic() + 3
            while not ready.is_set() and not stop.is_set() and time.monotonic() < until:
                client.loop(timeout=0.02)
            if not ready.is_set():
                record["error"] = "MQTTConnectTimeout"
            return client, record

        def finish(client, record):
            try:
                client.disconnect()
                client.loop_write()
                client.loop(timeout=0.02)
            except (OSError, RuntimeError):
                pass
            # Public socket close terminates any remaining connection, not a background thread.
            sock = client.socket()
            if sock:
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                    sock.close()
                except OSError:
                    pass
            record["closed_at"] = record.get("closed_at") or time.time()

        def send(client, record, payload, sequence, topic=None):
            with rate_lock:
                stop.wait(max(0, next_send[0] - time.monotonic()))
                next_send[0] = time.monotonic() + 1 / 120
            info = client.publish(topic or entry["topic"], json.dumps(payload), qos=1)
            until = time.monotonic() + 1
            while not info.is_published() and time.monotonic() < until and not stop.is_set():
                client.loop(timeout=0.01)
            record["actions"].append(
                dict(
                    sequence_number=sequence,
                    key_epoch=entry["key_epoch"],
                    sent_at=time.time(),
                    mqtt_ack=bool(info.is_published()),
                    payload_sha256=hashlib.sha256(
                        json.dumps(payload, sort_keys=True).encode()
                    ).hexdigest(),
                )
            )
            with lock:
                messages.append(
                    dict(
                        logical_device=name, key_epoch=entry["key_epoch"], sequence_number=sequence
                    )
                )

        client = None
        record = None
        try:
            # Replay preparation is a separately labeled normal TCP connection.
            if actor and config.scenario == "replay":
                packet, packet_sequence = make_packet()
                client, record = connection("normal")
                if record["authenticated"]:
                    send(client, record, packet, packet_sequence)
                    record["confirmed"] = True
                finish(client, record)
                client = None
                stop.wait(0.15)
            kind = config.scenario if actor else "normal"
            client, record = connection(kind)
            if actor and config.scenario == "bad_credentials":
                record["confirmed"] = record["auth_rejected"]
                stop.wait(0.05)
                return
            if not record["authenticated"]:
                return
            if not actor:
                record["confirmed"] = True
            while not stop.is_set() and time.monotonic() < deadline and count < 80:
                with lock:
                    if len(messages) >= 1900:
                        stop.set()
                        break
                if actor and config.scenario == "replay":
                    payload, seq = packet, packet_sequence
                else:
                    payload, seq = make_packet()
                if actor and config.scenario in {"tampered","wrong_epoch","wrong_sequence"}:
                    if config.scenario == "tampered":
                        raw = bytearray(base64.b64decode(payload["ciphertext"]))
                        raw[-1] ^= 1
                        payload["ciphertext"] = base64.b64encode(raw).decode()
                    else:
                        # Deliberate metadata forgery of one already-formed packet;
                        # never a second encryption with the same nonce.
                        ad = json.loads(base64.b64decode(payload["associated_data"]))
                        field = "key_epoch" if config.scenario == "wrong_epoch" else "sequence_number"
                        ad[field] += 1
                        payload["associated_data"] = base64.b64encode(json.dumps(ad,sort_keys=True,separators=(",",":")).encode()).decode()
                    try:
                        decode_packet(
                            payload if isinstance(payload, bytes) else json.dumps(payload).encode(),
                            entry["topic"],
                            registry,
                        )
                    except InvalidTelemetry:
                        record["local_crypto_rejection"] = True
                    else:
                        raise RuntimeError("Tamper unexpectedly authenticated")
                if not actor and config.scenario == "qos1_retry" and count == 0:
                    info = client.publish(entry["topic"], json.dumps(payload), qos=1)
                    client.loop_write()
                    sock = client.socket()
                    sock.shutdown(socket.SHUT_RDWR)
                    sock.close()
                    # Preserve Paho unacknowledged QoS1 state across reconnect; no new telemetry counter.
                    record["closed_at"] = time.time()
                    client.reconnect()
                    until = time.monotonic() + 2
                    while not info.is_published() and time.monotonic() < until:
                        client.loop(timeout=0.01)
                    record = next(
                        r for r in reversed(records) if r["client_id"] == record["client_id"]
                    )
                    record["confirmed"] = record["authenticated"]
                    record["qos_retry_ack"] = bool(info.is_published())
                    retry_dup += int(record["normal_retry_dup_observed"])
                    with lock:
                        messages.append(
                            dict(
                                logical_device=name,
                                key_epoch=entry["key_epoch"],
                                sequence_number=seq,
                            )
                        )
                else:
                    send(
                        client,
                        record,
                        payload,
                        seq,
                        "iot/sensors/lab000"
                        if actor and config.scenario == "forbidden_acl"
                        else None,
                    )
                count += 1
                if actor:
                    record["confirmed"] = (
                        True  # Additional independent corroboration is required by builder for ACL/replay/tamper.
                    )
                if actor and config.scenario == "forbidden_acl":
                    break
                if not actor and config.scenario in {"reconnect", "restart"} and count == 2:
                    finish(client, record)
                    client, record = connection("normal")
                    record["confirmed"] = record["authenticated"]
                period = config.interval * (
                    0.5
                    if (actor and config.scenario == "bounded_rate")
                    or (not actor and config.scenario == "normal_burst" and count % 5 < 3)
                    else 1
                )
                if actor and config.scenario == "pattern_change":
                    period = config.interval * (0.5 if count % 2 else 1.5)
                stop.wait(max(0.1, period + local.uniform(-config.jitter, config.jitter)))
        except Exception as e:
            with lock:
                errors.append(dict(actor_slot=index, error_type=type(e).__name__))
        finally:
            if client is not None:
                finish(client, record)

    with ThreadPoolExecutor(max_workers=config.clients) as executor:
        list(executor.map(lambda pair: worker(*pair), enumerate(selected)))
    ended = time.time()
    clock_drift = abs((ended - started) - (time.monotonic() - mono))
    result = dict(
        schema_version=1,
        experiment=config.payload(),
        experiment_started_at=started,
        experiment_finished_at=ended,
        clock=dict(
            source="shared host CLOCK_REALTIME, Docker time namespaces unchanged",
            precision_seconds=time.get_clock_info("time").resolution,
            wall_monotonic_drift_seconds=clock_drift,
            boundary_margin_seconds=max(0.00005, clock_drift * 2),
        ),
        devices=selected,
        connections=records,
        sent_messages=len(messages),
        messages=messages,
        errors=errors,
        generator_peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        generator_user_cpu_seconds=resource.getrusage(resource.RUSAGE_SELF).ru_utime,
        all_clients_stopped=all(r.get("closed_at") is not None for r in records),
        mode="CONTROLLED_LAB",
        telemetry_values="generated valid sensor values, not real physical ground truth",
    )
    (directory / "ground-truth.json").write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                "experiment_id": config.experiment_id,
                "sent_messages": len(messages),
                "connections": len(records),
                "errors": len(errors),
            }
        )
    )
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", required=True)
    args = p.parse_args()
    run(Experiment(**json.loads(Path(args.config).read_text())), "/research")


if __name__ == "__main__":
    main()

"""Isolated read-only broker fanout witness. No Ascon keys/payload persistence.
Candidate AD identity is UNTRUSTED until correlated with authenticated PG events.
"""

import argparse, base64, hashlib, json, os, re, signal, time, uuid
from pathlib import Path
from threading import Event
import paho.mqtt.client as mqtt
from src.mqtt_transport import configure_client
from src.telemetry import strict_json


def run(directory, duration):
    if not 3 <= duration <= 30:
        raise ValueError("Observer duration bound")
    os.umask(0o077)
    directory.mkdir(exist_ok=True, mode=0o700)
    if (directory / "mqtt-observer.json").exists():
        raise ValueError("Observer output immutable")
    (directory / "observer.pid").write_text(str(os.getpid()))
    stop = Event()
    events = []
    ready = False
    overflow = False
    for sig in [signal.SIGINT, signal.SIGTERM]:
        signal.signal(sig, lambda *_: stop.set())
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="evidence-" + uuid.uuid4().hex)
    configure_client(
        client,
        username="web",
        password_file="/run/observer/web.password",
        ca_file="/run/observer/ca.crt",
    )

    def connected(c, u, f, reason, p):
        if reason == 0:
            c.subscribe("iot/sensors/+", qos=1)

    def subscribed(c, u, mid, reasons, p):
        nonlocal ready
        if not any(r.is_failure for r in reasons):
            ready = True
            (directory / "observer-ready").touch()

    def message(c, u, msg):
        nonlocal overflow
        if not re.fullmatch(r"iot/sensors/lab\d{3}", msg.topic) or len(msg.payload) > 8192:
            return
        if len(events) >= 4000:
            overflow = True
            stop.set()
            return
        item = dict(
            at=time.time(), topic=msg.topic, candidate_identity=None, untrusted_metadata=True
        )
        try:
            body = strict_json(msg.payload)
            ad = strict_json(base64.b64decode(body["associated_data"], validate=True))
            item["candidate_identity"] = [
                ad[k] for k in ["device_id", "key_epoch", "sequence_number"]
            ]
            item["payload_sha256"] = hashlib.sha256(
                json.dumps(body, sort_keys=True).encode()
            ).hexdigest()
        except (ValueError, KeyError, TypeError):
            item["invalid_envelope"] = True
        events.append(item)

    client.on_connect = connected
    client.on_subscribe = subscribed
    client.on_message = message
    try:
        client.connect("broker", 8883, 30)
        deadline = time.monotonic() + duration
        while (
            time.monotonic() < deadline
            and not stop.is_set()
            and not (directory / "stop-observer").exists()
        ):
            client.loop(timeout=0.02)
    finally:
        client.disconnect()
        client.loop_write()
        (directory / "observer-ready").unlink(missing_ok=True)
    result = dict(
        schema_version=2,
        source="independent_read_only_mqtt_fanout",
        ready_observed=ready,
        overflow=overflow,
        events=events,
        payload_persisted=False,
        ascon_keys_available=False,
    )
    (directory / "mqtt-observer.json").write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--directory", type=Path, required=True)
    p.add_argument("--duration", type=float, required=True)
    a = p.parse_args()
    run(a.directory, a.duration)

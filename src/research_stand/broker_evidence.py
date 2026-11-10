"""Allowlisted broker-side evidence with Docker timestamps; no payload/password logs."""

import re
from datetime import datetime


def parse(log, started, finished):
    if len(log) > 8 * 1024**2:
        raise ValueError("Broker evidence log bound")
    denials = []
    sessions = []
    pending = []
    events = []
    for line in log.splitlines():
        parts = line.split(" ", 1)
        try:
            t = datetime.fromisoformat(parts[0].replace("Z", "+00:00")).timestamp()
        except ValueError:
            continue
        if not started <= t <= finished:
            continue
        body = parts[1]
        new = re.search(r"New connection from ([0-9.]+):(\d+) on port 8883", body)
        if new:
            pending.append(dict(ip=new[1], port=int(new[2]), opened_at=t))
        auth = re.search(
            r"New client connected from ([0-9.]+):(\d+) as (lab-[0-9a-f]+).*u'(device_lab\d{3})'",
            body,
        )
        if auth:
            matches = [p for p in pending if p["ip"] == auth[1] and p["port"] == int(auth[2])]
            if len(matches) == 1:
                p = matches[0]
                pending.remove(p)
                sessions.append(
                    dict(
                        **p,
                        client_id=auth[3],
                        username=auth[4],
                        auth_code=0,
                        authenticated_at=t,
                        events=[],
                    )
                )
        connack = re.search(r"Sending CONNACK to (lab-[0-9a-f]+) \(0, (\d+)\)", body)
        if connack and int(connack[2]) != 0:
            denials.append(dict(client_id=connack[1], code=int(connack[2]), at=t))
            candidates = [p for p in pending if 0 <= t - p["opened_at"] <= 1]
            if len(candidates) == 1:
                p = candidates[0]
                pending.remove(p)
                sessions.append(
                    dict(
                        **p,
                        client_id=connack[1],
                        username=None,
                        auth_code=int(connack[2]),
                        authenticated_at=t,
                        events=[],
                    )
                )
        pub = re.search(
            r"(Received|Denied) PUBLISH from (lab-[0-9a-f]+) \(d(\d), q(\d), r(\d), m(\d+), '([^']+)'",
            body,
        )
        if pub:
            current = [
                s
                for s in sessions
                if s["client_id"] == pub[2] and s["opened_at"] <= t and not s.get("closed_at")
            ]
            if len(current) == 1:
                # Topic only laboratory namespace; no raw credentials or data retained.
                topic = (
                    pub[7] if re.fullmatch(r"iot/sensors/lab\d{3}", pub[7]) else "outside_allowlist"
                )
                current[0]["events"].append(
                    dict(
                        kind="publish" if pub[1] == "Received" else "acl_denied",
                        at=t,
                        dup=int(pub[3]),
                        qos=int(pub[4]),
                        mid=int(pub[6]),
                        topic=topic,
                    )
                )
        close = re.search(
            r"Client (lab-[0-9a-f]+)(?: \[([0-9.]+):(\d+)\])? (?:disconnected|closed)", body
        )
        if close:
            if close[2] and not any(
                s["client_id"] == close[1] and s["ip"] == close[2] and s["port"] == int(close[3])
                for s in sessions
            ):
                pp = [
                    p
                    for p in pending
                    if p["ip"] == close[2]
                    and p["port"] == int(close[3])
                    and 0 <= t - p["opened_at"] <= 1
                ]
                dd = [d for d in denials if d["client_id"] == close[1] and 0 <= t - d["at"] <= 0.1]
                if len(pp) == 1 and len(dd) == 1:
                    p = pp[0]
                    pending.remove(p)
                    sessions.append(
                        dict(
                            **p,
                            client_id=close[1],
                            username=None,
                            auth_code=dd[0]["code"],
                            authenticated_at=dd[0]["at"],
                            events=[],
                        )
                    )
            active = [s for s in sessions if s["client_id"] == close[1] and not s.get("closed_at")]
            if close[2]:
                active = [s for s in active if s["ip"] == close[2] and s["port"] == int(close[3])]
            if len(active) == 1:
                active[0]["closed_at"] = t
    return dict(
        schema_version=2,
        parser_version="mosquitto-log-session-v2.1",
        source="docker_mosquitto_log",
        started_at=started,
        finished_at=finished,
        time_uncertainty_seconds=0.02,
        sessions=sessions,
        unbound_connections=len(pending),
    )

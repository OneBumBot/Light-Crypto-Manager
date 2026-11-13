"""Bounded laboratory settings. Target is the internal Compose broker only."""

from dataclasses import dataclass, asdict
import re

NORMAL = ["regular", "jitter", "reconnect", "restart", "normal_burst", "qos1_retry"]
VIOLATIONS = [
    "bad_credentials",
    "forbidden_acl",
    "replay",
    "tampered",
    "bounded_rate",
    "pattern_change",
    "wrong_epoch",
    "wrong_sequence",
]


@dataclass(frozen=True)
class Experiment:
    experiment_id: str
    scenario: str
    clients: int = 8
    duration: float = 6.0
    interval: float = 0.5
    jitter: float = 0.1
    seed: int = 1
    violation: bool = False
    schema_version: int = 1

    def validate(self):
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,60}", self.experiment_id):
            raise ValueError("Invalid experiment ID")
        if self.scenario not in (VIOLATIONS if self.violation else NORMAL):
            raise ValueError("Unsupported bounded scenario")
        if type(self.clients) is not int or not 2 <= self.clients <= 24:
            raise ValueError("Pilot client bound2..24")
        if type(self.seed) is not int or not 0 <= self.seed < 2**32:
            raise ValueError("Invalid reproducibility seed")
        for v, lo, hi in [(self.duration, 3, 20), (self.interval, 0.15, 2), (self.jitter, 0, 0.2)]:
            if type(v) not in (int, float) or not lo <= v <= hi:
                raise ValueError("Invalid duration/rate bound")
        if self.clients / self.interval > 120:
            raise ValueError("Aggregate message rate bound120/s")
        if (
            self.schema_version != 1
            or type(self.schema_version) is not int
            or type(self.violation) is not bool
        ):
            raise ValueError("Invalid experiment schema")
        return self

    def payload(self):
        return asdict(self.validate())

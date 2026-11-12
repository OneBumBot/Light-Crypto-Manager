"""Opt-in bounded observational journal; never used for nonce/control/replay state."""
import json
import os
import threading
import time
import uuid
from pathlib import Path


class ResearchJournal:
    def __init__(self, path=None, *, maximum=50000):
        if type(maximum) is not int or not 100 <= maximum <= 100000:
            raise ValueError('Bounded research journal required')
        self.path = Path(path) if path else None
        self.maximum = maximum
        self.lock = threading.Lock()
        self.count = 0
        self.boot = str(uuid.uuid4())
        self.exhausted = False
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            # Append across restarts. Never reset the authoritative SQLite file.
            self.count = sum(1 for _ in self.path.open()) if self.path.exists() else 0
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            self.file = os.fdopen(fd, 'a', buffering=1)
        else:
            self.file = None

    def record(self, kind, **fields):
        if not self.file:
            return
        with self.lock:
            if self.count >= self.maximum:
                self.exhausted = True
                return
            self.file.write(json.dumps(dict(kind=kind, boot=self.boot, wall_ns=time.time_ns(),
                                           monotonic_ns=time.monotonic_ns(), **fields))+'\n')
            self.count += 1

    def close(self):
        with self.lock:
            if self.file:
                self.file.close()
                self.file = None

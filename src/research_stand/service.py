"""Idle network namespace holder, graceful stop; no listener or background generator."""

import signal
from threading import Event

if __name__ == "__main__":
    stop = Event()
    for sig in [signal.SIGINT, signal.SIGTERM]:
        signal.signal(sig, lambda *_: stop.set())
    stop.wait()

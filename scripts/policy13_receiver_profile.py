"""Lab-only monotonic admission timing, preserving all original exceptions and ACKs."""
import json,time
from contextlib import contextmanager
from pathlib import Path
from src.brocker import mqtt_brocker as receiver
original=receiver.process_packet
recorded=0


class TimedEngine:
    def __init__(self,engine,records):self.engine=engine;self.records=records
    def __getattr__(self,name):return getattr(self.engine,name)
    @contextmanager
    def begin(self):
        start=time.perf_counter_ns();committed=False
        try:
            with self.engine.begin() as c:yield c
            committed=True
        finally:self.records.append(dict(nanoseconds=time.perf_counter_ns()-start,committed=committed))


def measured(packet,registry,engine,*args,**kwargs):
    global recorded
    transactions=[];start=time.perf_counter_ns();outcome='exception';kind=None
    try:
        result=original(packet,registry,TimedEngine(engine,transactions),*args,**kwargs);outcome='admitted' if result is not None else 'replay';return result
    except Exception as error:
        kind=type(error).__name__;raise
    finally:
        elapsed=time.perf_counter_ns()-start
        if recorded<100000:
            with Path('/tmp/policy13-admission.jsonl').open('a') as f:f.write(json.dumps(dict(finished_wall_ns=time.time_ns(),total_ns=elapsed,transactions=transactions,outcome=outcome,error_class=kind))+'\n')
            recorded+=1
receiver.process_packet=measured
if __name__=='__main__':receiver.main()

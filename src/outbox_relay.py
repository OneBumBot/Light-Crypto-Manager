"""At-least-once delivery with lease fencing; no PG transaction during Mongo IO."""
import argparse
import logging
import os
import signal
from pathlib import Path
from threading import Event
from sqlalchemy import create_engine
from src.runtime import database_url
from src.mongo_repository import MongoRepository
from src.outbox import claim, finish, cleanup, requeue_dead

logger = logging.getLogger(__name__)


def deliver_one(engine, repository, *, after_write=None, lease_seconds=30, max_attempts=12,
                backoff_base=1, backoff_cap=300):
    event = claim(engine, lease_seconds=lease_seconds, max_attempts=max_attempts)
    if event is None:
        return False
    try:
        repository.store(event['payload'])
        if after_write:
            after_write(event)  # Fault injection seam; BaseException simulates process death.
    except Exception as error:
        finish(engine,event,error,max_attempts=max_attempts,backoff_base=backoff_base,backoff_cap=backoff_cap)
        logger.warning('Telemetry delivery failed (%s)',type(error).__name__)
    else:
        finish(engine,event)
    return True


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--requeue-dead', metavar='EVENT_ID')
    args=parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    engine=create_engine(database_url(),pool_pre_ping=True)
    repository=None
    try:
        if args.requeue_dead:
            print('Requeued events:',requeue_dead(engine,args.requeue_dead))
            return
        repository=MongoRepository()
        stop=Event()
        for sig in (signal.SIGINT,signal.SIGTERM):
            signal.signal(sig,lambda *_:stop.set())
        while not stop.is_set():
            try:
                worked=deliver_one(engine,repository,
                    max_attempts=int(os.environ.get('OUTBOX_MAX_ATTEMPTS','12')))
                cleanup(engine,int(os.environ.get('OUTBOX_RETENTION_DAYS','0')))
            except Exception as error:
                logger.error('Relay database unavailable (%s)',type(error).__name__)
                worked=False
            Path('/tmp/relay-ready').touch()
            if not worked:
                stop.wait(0.5)
    finally:
        if repository: repository.close()
        engine.dispose()

if __name__=='__main__':
    main()

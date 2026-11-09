"""Optional research inference worker, outside MQTT ingestion and outbox relay."""
import argparse
import logging
import os
from pathlib import Path
import signal
from threading import Event
import time
import math
import pandas as pd
from sqlalchemy import create_engine
from src.runtime import database_url
from src.mongo_repository import MongoRepository
from src.ml_storage import claim_one,complete,model_status,prune_feed
from .artifacts import load
from .schema import safe_name
from .telemetry_features import one_window,UnknownDevice

logger=logging.getLogger(__name__)


def evaluate_one(engine,repository,manifest,pipeline,*,after_score=None):
    if manifest['task']!='telemetry_anomaly':raise ValueError('Online network IDS is forbidden without compatible collector')
    event=claim_one(engine,manifest)
    if event is None:return False
    start=time.perf_counter();prep_ms=0;inference_ms=0
    try:
        identity={k:event[k] for k in ['device_id','key_epoch','sequence_number']}
        target=repository.collection.find_one(identity,max_time_ms=2000)
        if target is None:
            complete(engine,event,'retry',diagnostic='SourceNotVisibleOrExpired')
            return True
        window=manifest['preprocessing']['window']
        # Receiver accepts monotone sequence per epoch; arrival history is bounded.
        history=list(repository.collection.find(dict(device_id=event['device_id'],key_epoch=event['key_epoch'],
            sequence_number={'$lt':event['sequence_number']})).sort('sequence_number',-1).limit(window).max_time_ms(2000))
        history.reverse()
        features,status=one_window(target,history,window,manifest['preprocessing']['expected_interval'])
        prep_ms=(time.perf_counter()-start)*1000
        if features is None:
            complete(engine,event,status,diagnostic='CausalWindowUnavailable',prepare_ms=prep_ms)
            return True
        if event['device_id'] not in pipeline.named_steps['features'].baselines_:
            complete(engine,event,'unknown_device',diagnostic='NoTrainedDeviceBaseline',prepare_ms=prep_ms)
            return True
        begin=time.perf_counter()
        score=float(-pipeline.score_samples(pd.DataFrame([features]))[0])
        inference_ms=(time.perf_counter()-begin)*1000
        upper=manifest['preprocessing']['score_range'][1]
        if not math.isfinite(score) or score<0 or (upper is not None and score>upper):raise ValueError('Invalid model score')
        if after_score:after_score(event)
        complete(engine,event,'ok',score=score,threshold=manifest['threshold'],is_anomaly=score>=manifest['threshold'],
            prepare_ms=prep_ms,inference_ms=inference_ms)
    except UnknownDevice:
        complete(engine,event,'unknown_device',diagnostic='NoTrainedDeviceBaseline',prepare_ms=prep_ms)
    except (ValueError,TypeError,KeyError,OverflowError):
        complete(engine,event,'invalid_history',diagnostic='FeatureContractRejected',prepare_ms=prep_ms)
    except Exception as error:
        complete(engine,event,'retry',diagnostic=type(error).__name__[:80],prepare_ms=prep_ms,inference_ms=inference_ms)
        logger.warning('ML observation deferred (%s)',type(error).__name__)
    return True


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prune-feed-days',type=int)
    parser.add_argument('--once',action='store_true')
    args=parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    engine=create_engine(database_url(),pool_pre_ping=True)
    repo=None
    try:
        if args.prune_feed_days:
            print('Explicitly pruned markers:',prune_feed(engine,args.prune_feed_days));return
        model_id=safe_name(os.environ.get('ML_MODEL_ID','telemetry-statistical'))
        version=safe_name(os.environ.get('ML_MODEL_VERSION','1.0.0'))
        root=os.environ.get('ML_MODELS_DIR','/models')
        batch=int(os.environ.get('ML_BATCH_SIZE','16'))
        if not 1<=batch<=128:raise ValueError('ML batch size outside bound')
        stop=Event();manifest=None;pipeline=None
        for sig in [signal.SIGINT,signal.SIGTERM]:signal.signal(sig,lambda *_:stop.set())
        repo=MongoRepository('history')
        while not stop.is_set():
            try:
                if os.environ.get('ML_ALLOW_RESEARCH','0')!='1':
                    model_status(engine,model_id,version,'disabled',diagnostic='ResearchOptInRequired')
                else:
                    if pipeline is None:manifest,pipeline=load(root,model_id,version)
                    if manifest['task']!='telemetry_anomaly':raise ValueError('Telemetry model required')
                    available=model_status(engine,model_id,version,'available',manifest)
                    if available:
                        heartbeat=time.monotonic()
                        for _ in range(batch):
                            if stop.is_set() or not evaluate_one(engine,repo,manifest,pipeline):break
                            if time.monotonic()-heartbeat>10:
                                model_status(engine,model_id,version,'available',manifest)
                                heartbeat=time.monotonic()
                Path('/tmp/ml-heartbeat').touch()
            except Exception as error:
                logger.warning('ML model unavailable (%s)',type(error).__name__)
                pipeline=None
                try:model_status(engine,model_id,version,'unavailable',diagnostic=type(error).__name__[:80])
                except Exception:pass
            if args.once:break
            stop.wait(1)
    finally:
        if repo:repo.close()
        engine.dispose()

if __name__=='__main__':main()

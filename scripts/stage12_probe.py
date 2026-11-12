"""Bounded source-identity reconciliation; not a telemetry producer."""
import json,sys
from datetime import datetime,timezone
from sqlalchemy import create_engine,select,tuple_
from src.runtime import database_url
from src.outbox import outbox
from src.mongo_repository import MongoRepository


def main():
    ids=json.load(sys.stdin)
    if type(ids) is not list or not 1<=len(ids)<=500:raise ValueError('Bounded source cohort required')
    engine=create_engine(database_url());keys=[(x['device'],x['epoch'],x['sequence']) for x in ids]
    with engine.connect() as c:
        rows=[dict(r) for r in c.execute(select(outbox).where(tuple_(outbox.c.device_id,outbox.c.key_epoch,outbox.c.sequence_number).in_(keys)).limit(500)).mappings()]
    repo=MongoRepository('relay')
    mongo_ids=[f'{d}:{e}:{s}' for d,e,s in keys]
    try:stored=repo.collection.count_documents({'_id':{'$in':mongo_ids}},maxTimeMS=2000)
    finally:repo.close();engine.dispose()
    safe=[]
    for r in rows:
        p=r['payload'];safe.append(dict(device=r['device_id'],epoch=r['key_epoch'],sequence=r['sequence_number'],profile=p['crypto_profile'],outbox_id=r['id'],status=r['status'],sensor_to_receiver_created_ms=(r['created_at']-datetime.fromisoformat(p['measured_at'])).total_seconds()*1000,pg_created_to_delivery_ms=(r['delivered_at']-r['created_at']).total_seconds()*1000 if r['delivered_at'] else None))
    print(json.dumps(dict(source_formed=len(keys),pg_unique=len(rows),mongo_stored=stored,rows=safe)))

if __name__=='__main__':main()

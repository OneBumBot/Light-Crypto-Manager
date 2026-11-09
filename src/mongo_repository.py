"""One writer: idempotent insert, strict contract, bounded authorized reads."""
from datetime import datetime, timezone
import os
from pathlib import Path
from bson import BSON
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError
from pymongo.write_concern import WriteConcern
from src.telemetry import DEVICE, PROFILE, validate_sensor, positive, exact

MAX_DOCUMENT_BYTES = 8192


def utc_millis(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if not isinstance(value, datetime) or value.utcoffset() != timezone.utc.utcoffset(None):
        raise ValueError('UTC datetime required')
    return value.astimezone(timezone.utc).replace(microsecond=(value.microsecond//1000)*1000)


def document(payload):
    exact(payload, ['device_id','key_epoch','sequence_number','measured_at','received_at',
                    'crypto_profile','temperature','humidity','sensors'])
    device = payload['device_id']
    if type(device) is not str or not DEVICE.fullmatch(device):
        raise ValueError('Invalid device')
    positive(payload['key_epoch'],2**31-1)
    positive(payload['sequence_number'])
    if payload['crypto_profile'] != PROFILE or payload['sensors'] != {}:
        raise ValueError('Unsupported telemetry schema')
    validate_sensor(dict(temperature=payload['temperature'],humidity=payload['humidity'],timestamp=payload['measured_at']))
    result = dict(payload)
    result['measured_at'] = utc_millis(payload['measured_at'])
    result['received_at'] = utc_millis(payload['received_at'])
    result['_id'] = f"{device}:{payload['key_epoch']}:{payload['sequence_number']}"
    if len(BSON.encode(result)) > MAX_DOCUMENT_BYTES:
        raise ValueError('Telemetry document too large')
    return result


class TelemetryConflict(RuntimeError):
    pass


class MongoRepository:
    def __init__(self, role='relay', *, host=None, password_file=None):
        if role not in ('relay','history'):
            raise ValueError('Unknown database role')
        self.client = MongoClient(host or os.environ.get('MONGO_HOST','mongo'),
            port=int(os.environ.get('MONGO_PORT','27017')), username=role,
            password=Path(password_file or os.environ['MONGO_PASSWORD_FILE']).read_text().strip(),
            authSource='telemetry', tz_aware=True, retryWrites=False,
            serverSelectionTimeoutMS=2000, connectTimeoutMS=2000, socketTimeoutMS=3000,
            timeoutMS=5000, maxPoolSize=10)
        self.collection = self.client.telemetry.get_collection('measurements',
            write_concern=WriteConcern(w='majority', j=True, wtimeout=3000))

    def close(self):
        self.client.close()

    def store(self, payload):
        doc = document(payload)
        try:
            self.collection.insert_one(doc)
            return True
        except DuplicateKeyError:
            # A duplicate is success only if the durable record is identical.
            if self.collection.find_one({'_id':doc['_id']}) != doc:
                raise TelemetryConflict('Telemetry identity collision') from None
            return False

    def history(self, *, device=None, start=None, end=None, limit=100, offset=0):
        if type(limit) is not int or not 1 <= limit <= 500 or type(offset) is not int or not 0 <= offset <= 10000:
            raise ValueError('Invalid pagination')
        query = {}
        if device is not None:
            if type(device) is not str or not DEVICE.fullmatch(device):
                raise ValueError('Invalid device')
            query['device_id'] = device
        if start is not None or end is not None:
            bounds={}
            if start is not None: bounds['$gte']=utc_millis(start)
            if end is not None: bounds['$lte']=utc_millis(end)
            if start is not None and end is not None and bounds['$gte'] > bounds['$lte']:
                raise ValueError('Invalid date range')
            query['measured_at']=bounds
        rows=list(self.collection.find(query).sort([('measured_at',DESCENDING),('_id',DESCENDING)])
                  .skip(offset).limit(limit).max_time_ms(2000))
        return [{k:(v.isoformat() if isinstance(v,datetime) else v) for k,v in row.items() if k!='_id'} for row in rows]

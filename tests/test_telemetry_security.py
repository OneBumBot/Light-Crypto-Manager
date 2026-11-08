import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json

import pytest
from sqlalchemy import select, func
from src.telemetry import (encode_packet,decode_packet,InvalidTelemetry,canonical,MAX_PACKET_BYTES)
from src.sequence import next_sequence
from src.web.ascon.ascon import ascon_encrypt
from src.brocker.mqtt_brocker import process_packet
from src.replay import replay_state
from src.web.models import Anomaly
from test_postgres import seed_device

TOPIC='iot/sensors/raspb1'


def sensor():
    return {'temperature':65,'humidity':50,'timestamp':datetime.now(timezone.utc).isoformat()}


def test_sequence_persists_and_is_concurrent(tmp_path):
    path=tmp_path/'sequence.db'
    with ThreadPoolExecutor(max_workers=8) as pool:
        values=list(pool.map(lambda _:next_sequence(path,'raspb1',1),range(24)))
    assert sorted(values)==list(range(1,25))
    assert next_sequence(path,'raspb1',1)==25
    assert next_sequence(path,'raspb1',2)==1


@pytest.mark.parametrize('change', [
    {'schema_version':1}, {'schema_version':True}, {'profile':'Ascon-128'},
    {'nonce':'!'}, {'nonce':base64.b64encode(b'x'*15).decode()},
    {'ciphertext':base64.b64encode(b'x'*15).decode()}, {'nonce':None},
    {'unexpected':'value'}, {'associated_data':'%%%%'},
])
def test_envelope_validation(registry,change):
    value=encode_packet(sensor(),registry,'raspb1',1)
    value.update(change)
    with pytest.raises(InvalidTelemetry): decode_packet(value,TOPIC,registry)


@pytest.mark.parametrize('raw', [b'[]',b'null',b'no-json',b'\xff',b'{}',b'{'*1100,
                                b'x'*(MAX_PACKET_BYTES+1), b'{"a":1,"a":2}'])
def test_bad_json_and_size(registry,raw):
    with pytest.raises(InvalidTelemetry): decode_packet(raw,TOPIC,registry)


@pytest.mark.parametrize('field,value', [('sequence_number',0),('sequence_number',True),
    ('sequence_number',2**63),('key_epoch',0),('device_id','other'),('topic','iot/sensors/other'),
    ('sequence_number',2),('profile','other')])
def test_metadata_cannot_be_modified(registry,field,value):
    packet=encode_packet(sensor(),registry,'raspb1',1)
    ad=json.loads(base64.b64decode(packet['associated_data']))
    ad[field]=value
    packet['associated_data']=base64.b64encode(canonical(ad)).decode()
    with pytest.raises(InvalidTelemetry): decode_packet(packet,TOPIC,registry)


def test_topic_key_and_epoch_binding(registry):
    packet=encode_packet(sensor(),registry,'raspb1',1)
    with pytest.raises(InvalidTelemetry): decode_packet(packet,'iot/sensors/smoke',registry)
    registry['raspb1']['key_hex']='ff'*16
    with pytest.raises(InvalidTelemetry): decode_packet(packet,TOPIC,registry)
    registry['raspb1']['key_epoch']=2
    with pytest.raises(InvalidTelemetry): decode_packet(packet,TOPIC,registry)


@pytest.mark.parametrize('field,value', [('temperature',True),('temperature',151),('temperature',-81),
    ('humidity',101),('humidity',-1),('humidity','50'),('timestamp','2026-01-01'),
    ('temperature',float('nan')),('humidity',float('inf'))])
def test_authenticated_bad_telemetry_rejected(registry,field,value):
    packet=encode_packet(sensor(),registry,'raspb1',1)
    data=sensor();data[field]=value
    ad=base64.b64decode(packet['associated_data']);nonce=base64.b64decode(packet['nonce'])
    ct=ascon_encrypt(bytes.fromhex(registry['raspb1']['key_hex']),nonce,ad,json.dumps(data).encode())
    packet['ciphertext']=base64.b64encode(ct).decode()
    with pytest.raises(InvalidTelemetry): decode_packet(packet,TOPIC,registry)


@pytest.mark.postgres
def test_atomic_duplicate_admission(postgres_db,registry):
    seed_device(postgres_db)
    engine=postgres_db.db.engine
    packet=encode_packet(sensor(),registry,'raspb1',1)
    with ThreadPoolExecutor(max_workers=8) as pool:
        values=list(pool.map(lambda _:process_packet(packet,registry,engine,TOPIC),range(16)))
    assert sum(value is not None for value in values)==1
    assert postgres_db.db.session.scalar(select(func.count()).select_from(Anomaly))==1
    with engine.connect() as connection:
        assert connection.execute(select(replay_state.c.last_sequence)).scalar_one()==1


@pytest.mark.postgres
def test_replay_state_survives_new_engine(postgres_db,registry):
    from sqlalchemy import create_engine
    seed_device(postgres_db)
    engine=postgres_db.db.engine
    packet=encode_packet(sensor(),registry,'raspb1',1)
    assert process_packet(packet,registry,engine,TOPIC) is not None
    replacement=create_engine(engine.url)
    try: assert process_packet(packet,registry,replacement,TOPIC) is None
    finally: replacement.dispose()


def test_legacy_format_has_no_fallback(registry):
    packet=encode_packet(sensor(),registry,'raspb1',1)
    old={key:packet[key] for key in ['nonce','associated_data','ciphertext']}
    old['algorithm']='Ascon-AEAD128'
    with pytest.raises(InvalidTelemetry): decode_packet(old,TOPIC,registry)


@pytest.mark.postgres
def test_consumers_have_independent_replay_state(postgres_db,registry):
    from src.replay import admit
    message=decode_packet(encode_packet(sensor(),registry,'raspb1',1),TOPIC,registry)
    for consumer in ['receiver','web']:
        with postgres_db.db.engine.begin() as connection:
            assert admit(connection,message,consumer)
            assert not admit(connection,message,consumer)

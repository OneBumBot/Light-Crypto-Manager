"""Bounded, authenticated telemetry v2. No legacy packets are accepted."""
import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re

from src.crypto_profiles import ASCON, AES, PROFILES, BY_ALGORITHM, encrypt, decrypt
from cryptography.exceptions import InvalidTag

MAX_PACKET_BYTES = 8192
MAX_SEQUENCE = 2**63-1
PROFILE = 'Ascon-AEAD128'
DEVICE = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,47}\Z')


class InvalidTelemetry(ValueError):
    pass


def reject():
    raise InvalidTelemetry('Invalid authenticated telemetry')


def strict_json(raw):
    def pairs(items):
        result={}
        for k,v in items:
            if k in result: reject()
            result[k]=v
        return result
    try:
        return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _: reject())
    except (ValueError,TypeError,UnicodeError,RecursionError):
        reject()


def exact(value, fields):
    if type(value) is not dict or set(value)!=set(fields): reject()


def positive(value, maximum=MAX_SEQUENCE):
    if type(value) is not int or not 1<=value<=maximum: reject()


def validate_sensor(sensor):
    exact(sensor,['temperature','humidity','timestamp'])
    for field,low,high in [('temperature',-80,150),('humidity',0,100)]:
        value=sensor[field]
        if type(value) not in (int,float) or not low<=value<=high or not math.isfinite(value): reject()
    if type(sensor['timestamp']) is not str or len(sensor['timestamp'])>40: reject()
    try:
        timestamp=datetime.fromisoformat(sensor['timestamp'])
        if timestamp.utcoffset()!=timezone.utc.utcoffset(None): reject()
    except (TypeError,ValueError,OverflowError): reject()
    return sensor


def validate_registry(registry):
    if type(registry) is not dict or not registry: reject()
    seen=set()
    database_ids=set()
    for device,entry in registry.items():
        if not DEVICE.fullmatch(device): reject()
        exact(entry,['topic','key_epoch','database_device_id','key_hex'] + (['telemetry_keys'] if 'telemetry_keys' in entry else []))
        if entry['topic']!='iot/sensors/'+device: reject()
        positive(entry['key_epoch'],2**31-1)
        positive(entry['database_device_id'],2**31-1)
        if entry['database_device_id'] in database_ids: reject()
        database_ids.add(entry['database_device_id'])
        try: key=bytes.fromhex(entry['key_hex'])
        except (ValueError,TypeError): reject()
        if len(key)!=16 or len(entry['key_hex'])!=32 or key in seen: reject()
        seen.add(key)
        if 'telemetry_keys' in entry:
            exact(entry['telemetry_keys'], ['AES-128-GCM'])
            try: aes=bytes.fromhex(entry['telemetry_keys']['AES-128-GCM'])
            except (ValueError,TypeError): reject()
            if len(aes)!=16 or len(entry['telemetry_keys']['AES-128-GCM'])!=32 or aes in seen: reject()
            seen.add(aes)
    return registry


def load_registry(path=None):
    path=path or os.environ.get('DEVICE_REGISTRY_FILE')
    if not path: raise ValueError('DEVICE_REGISTRY_FILE is required')
    return validate_registry(strict_json(Path(path).read_bytes()))


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def encode_packet(sensor, registry, device_id, sequence_number, *, profile=ASCON):
    validate_registry(registry)
    if device_id not in registry: reject()
    positive(sequence_number)
    validate_sensor(sensor)
    entry=registry[device_id]
    if profile not in PROFILES: reject()
    algorithm=PROFILES[profile]['algorithm']
    key=entry['key_hex'] if profile==ASCON else entry.get('telemetry_keys',{}).get(algorithm)
    if key is None: reject()
    metadata={'device_id':device_id,'topic':entry['topic'],'key_epoch':entry['key_epoch'],
              'sequence_number':sequence_number,'schema_version':2,'profile':algorithm}
    ad=canonical(metadata)
    nonce=os.urandom(16) if profile==ASCON else entry['key_epoch'].to_bytes(4,'big')+sequence_number.to_bytes(8,'big')
    ciphertext=encrypt(profile,bytes.fromhex(key),nonce,ad,canonical(sensor))
    return {'schema_version':2,'profile':algorithm,'nonce':base64.b64encode(nonce).decode(),
            'associated_data':base64.b64encode(ad).decode(),
            'ciphertext':base64.b64encode(ciphertext).decode()}


@dataclass(frozen=True)
class VerifiedTelemetry:
    device_id: str
    key_epoch: int
    sequence_number: int
    database_device_id: int
    sensor: dict
    profile: str = PROFILE


def decode_packet(raw, topic, registry):
    if isinstance(raw,dict): raw=canonical(raw)
    if isinstance(raw,str): raw=raw.encode()
    if type(raw) is not bytes or not 1<=len(raw)<=MAX_PACKET_BYTES: reject()
    packet=strict_json(raw)
    exact(packet,['schema_version','profile','nonce','associated_data','ciphertext'])
    if type(packet['schema_version']) is not int or packet['schema_version']!=2 or packet['profile'] not in BY_ALGORITHM: reject()
    def decode(name, maximum):
        value=packet[name]
        if type(value) is not str or len(value)>maximum*2: reject()
        try: result=base64.b64decode(value,validate=True)
        except (ValueError,UnicodeError): reject()
        if len(result)>maximum: reject()
        return result
    nonce=decode('nonce',16)
    ad=decode('associated_data',1024)
    ciphertext=decode('ciphertext',4096)
    profile=BY_ALGORITHM[packet['profile']]
    if len(nonce)!=PROFILES[profile]['nonce_bytes'] or len(ciphertext)<16: reject()
    metadata=strict_json(ad)
    exact(metadata,['device_id','topic','key_epoch','sequence_number','schema_version','profile'])
    device=metadata['device_id']
    if type(device) is not str or not DEVICE.fullmatch(device) or device not in registry: reject()
    positive(metadata['sequence_number'])
    positive(metadata['key_epoch'],2**31-1)
    entry=registry[device]
    if type(metadata['schema_version']) is not int or metadata['schema_version']!=2 or metadata['profile']!=packet['profile']: reject()
    if topic!=entry['topic'] or metadata['topic']!=topic or metadata['key_epoch']!=entry['key_epoch']: reject()
    key_hex=entry['key_hex'] if profile==ASCON else entry.get('telemetry_keys',{}).get(packet['profile'])
    if not key_hex: reject()
    key=bytes.fromhex(key_hex)
    if profile==AES and nonce!=metadata['key_epoch'].to_bytes(4,'big')+metadata['sequence_number'].to_bytes(8,'big'): reject()
    try: plaintext=decrypt(profile,key,nonce,ad,ciphertext)
    except (InvalidTag,ValueError): reject()
    sensor=validate_sensor(strict_json(plaintext))
    return VerifiedTelemetry(device,metadata['key_epoch'],metadata['sequence_number'],
                             entry['database_device_id'],sensor,packet['profile'])

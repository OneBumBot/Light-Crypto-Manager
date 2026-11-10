"""LCM control v2, HMAC-SHA-256 authenticated canonical JSON, no secret payloads.
Separate preprovisioned keys per direction. TLS provides confidentiality.
"""
import hashlib
import hmac
import re
import uuid
from datetime import datetime,timezone,timedelta
from src.telemetry import canonical,strict_json,DEVICE,positive
from src.crypto_profiles import PROFILES

DOMAIN='LCM-CONTROL-HMAC-SHA256-v2'
CONTROLLER='lcm-manual-controller'
MAX_BYTES=8192


def utc(value):
    if type(value) is not str or len(value)>40:raise ValueError('Invalid UTC time')
    t=datetime.fromisoformat(value)
    if t.utcoffset()!=timedelta(0):raise ValueError('UTC required')
    return t


def uid(value):
    if type(value) is not str or str(uuid.UUID(value))!=value:raise ValueError('Canonical UUID required')
    return value


def exact(value,fields):
    if type(value) is not dict or set(value)!=set(fields):raise ValueError('Control schema mismatch')


def topic(device,direction):
    if type(device) is not str or not DEVICE.fullmatch(device):raise ValueError('Invalid device')
    return f'lcm/control/{device}/'+('command' if direction=='controller' else 'status')


def validate(body,now=None):
    exact(body,['schema_version','message_id','device_id','kind','created_at','expires_at','data'])
    if type(body['schema_version']) is not int or body['schema_version']!=2:raise ValueError('Control version')
    uid(body['message_id']);topic(body['device_id'],'device')
    now=now or datetime.now(timezone.utc)
    start=utc(body['created_at']);end=utc(body['expires_at'])
    if not 0<(end-start).total_seconds()<=300 or start>now+timedelta(seconds=5) or end<=now:raise ValueError('Control expired/future')
    d=body['data'];kind=body['kind']
    if kind=='command':
        exact(d,['command_id','transition_id','correlation_id','command_type','phase','requested_profile','source_version','controller_identity','profile_config_version','key_reference','command_epoch','command_sequence'])
        for f in ['command_id','transition_id','correlation_id']:uid(d[f])
        if d['command_id']!=body['message_id'] or d['command_type']!='set_profile' or d['phase'] not in ['PREPARE','ACTIVATE'] or d['controller_identity']!=CONTROLLER:raise ValueError('Command identity')
        if d['requested_profile'] not in PROFILES or d['source_version']!='admin-v1' or type(d['profile_config_version']) is not int or d['profile_config_version']!=1:raise ValueError('Unsupported profile/source')
        positive(d['command_epoch'],2**31-1);positive(d['command_sequence'])
        if type(d['key_reference']) is not str or d['key_reference']!=d['requested_profile']+':'+str(d['command_epoch']):raise ValueError('Key reference')
    elif kind=='ack':
        exact(d,['command_id','transition_id','correlation_id','command_epoch','command_sequence','requested_profile','phase','result','command_sha256'])
        for f in ['command_id','transition_id','correlation_id']:uid(d[f])
        positive(d['command_epoch'],2**31-1);positive(d['command_sequence'])
        if d['requested_profile'] not in PROFILES or d['phase'] not in ['PREPARE','ACTIVATE'] or d['result'] not in ['READY','DEVICE_APPLIED','UNSUPPORTED','FAILED']:raise ValueError('Invalid ACK')
        if type(d['command_sha256']) is not str or not re.fullmatch('[0-9a-f]{64}',d['command_sha256']):raise ValueError('ACK digest')
    elif kind=='lease_request':
        exact(d,['boot_id','key_epoch','local_profile'])
        uid(d['boot_id']);positive(d['key_epoch'],2**31-1)
        if d['local_profile'] not in PROFILES:raise ValueError('Unsupported local profile')
    elif kind=='lease_grant':
        exact(d,['boot_id','request_id','key_epoch','first_sequence','last_sequence','effective_profile','pending_profile','command_floor'])
        uid(d['boot_id']);uid(d['request_id']);positive(d['key_epoch'],2**31-1)
        positive(d['first_sequence'],2**32-1);positive(d['last_sequence'],2**32-1)
        if d['first_sequence']>d['last_sequence'] or d['last_sequence']-d['first_sequence']>=10000:raise ValueError('Lease bounds')
        if d['effective_profile'] not in [None,*PROFILES] or d['pending_profile'] not in [None,*PROFILES] or type(d['command_floor']) is not int or d['command_floor']<0:raise ValueError('Lease configuration')
    else:raise ValueError('Unknown control kind')
    return body


def message(device,kind,data,*,now=None,ttl=120,message_id=None):
    now=now or datetime.now(timezone.utc)
    return validate(dict(schema_version=2,message_id=message_id or str(uuid.uuid4()),device_id=device,kind=kind,
        created_at=now.isoformat(),expires_at=(now+timedelta(seconds=ttl)).isoformat(),data=data),now)


def seal(body,key,direction,*,now=None):
    validate(body,now)
    if len(key)!=32 or direction not in ['controller','device']:raise ValueError('Control key/direction')
    if (body['kind'] in ['command','lease_grant']) != (direction=='controller'):raise ValueError('Wrong control direction')
    signed=dict(domain=DOMAIN,direction=direction,topic=topic(body['device_id'],direction),body=body)
    return canonical(dict(**signed,mac=hmac.new(key,canonical(signed),hashlib.sha256).hexdigest()))


def open_message(raw,key,direction,device,actual_topic,*,now=None):
    if type(raw) is not bytes or not 1<=len(raw)<=MAX_BYTES or len(key)!=32:raise ValueError('Control bounds')
    value=strict_json(raw);exact(value,['domain','direction','topic','body','mac'])
    mac=value.pop('mac')
    expected=hmac.new(key,canonical(value),hashlib.sha256).hexdigest()
    if type(mac) is not str or not hmac.compare_digest(mac,expected):raise ValueError('Control authentication failed')
    if value['domain']!=DOMAIN or value['direction']!=direction or value['topic']!=topic(device,direction) or actual_topic!=value['topic']:raise ValueError('Control domain/device binding')
    body=validate(value['body'],now)
    if body['device_id']!=device or (body['kind'] in ['command','lease_grant'])!=(direction=='controller'):raise ValueError('Control subject')
    return body

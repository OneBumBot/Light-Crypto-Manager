"""Private provisioned material; never log values or expose in HTTP."""
import os
from pathlib import Path
from src.telemetry import strict_json,validate_registry
from .protocol import exact
from src.crypto_profiles import ASCON,AES,KUZ,PROFILES,BY_ALGORITHM


def load(path=None):
    p=Path(path or os.environ['CONTROL_KEYS_FILE'])
    if p.stat().st_mode & 0o077:raise ValueError('Private control file permissions required')
    value=strict_json(p.read_bytes());seen=set()
    for device,e in value.items():
        exact(e,['registry','command_key','status_key','capabilities','command_epoch'])
        validate_registry({device:e['registry']})
        if type(e['command_epoch']) is not int or e['command_epoch']!=e['registry']['key_epoch']:raise ValueError('Explicit equal provisioning epochs required')
        if type(e['capabilities']) is not list or not e['capabilities'] or any(type(x) is not str or x not in PROFILES for x in e['capabilities']):raise ValueError('Capabilities')
        if AES in e['capabilities'] and 'AES-128-GCM' not in e['registry'].get('telemetry_keys',{}):raise ValueError('Missing AES telemetry key')
        for target in e['capabilities']:
            if target!=ASCON and PROFILES[target]['algorithm'] not in e['registry'].get('telemetry_keys',{}):raise ValueError('Missing profile key')
        keys=[(e['registry']['key_hex'],16),*[(v,PROFILES[BY_ALGORITHM[k]]['key_bytes']) for k,v in e['registry'].get('telemetry_keys',{}).items()],(e['command_key'],32),(e['status_key'],32)]
        for key,size in keys:
            b=bytes.fromhex(key)
            if len(b)!=size or b in seen:raise ValueError('Keys must be independent')
            seen.add(b)
    return value

"""Private provisioned material; never log values or expose in HTTP."""
import os
from pathlib import Path
from src.telemetry import strict_json,validate_registry
from .protocol import exact
from src.crypto_profiles import ASCON,AES


def load(path=None):
    p=Path(path or os.environ['CONTROL_KEYS_FILE'])
    if p.stat().st_mode & 0o077:raise ValueError('Private control file permissions required')
    value=strict_json(p.read_bytes());seen=set()
    for device,e in value.items():
        exact(e,['registry','command_key','status_key','capabilities','command_epoch'])
        validate_registry({device:e['registry']})
        if e['command_epoch']!=e['registry']['key_epoch']:raise ValueError('Explicit equal provisioning epochs required')
        if type(e['capabilities']) is not list or not e['capabilities'] or any(x not in [ASCON,AES] for x in e['capabilities']):raise ValueError('Capabilities')
        if AES in e['capabilities'] and 'AES-128-GCM' not in e['registry'].get('telemetry_keys',{}):raise ValueError('Missing AES telemetry key')
        keys=[e['registry']['key_hex'],*e['registry'].get('telemetry_keys',{}).values(),e['command_key'],e['status_key']]
        for index,key in enumerate(keys):
            b=bytes.fromhex(key)
            if len(b)!=(32 if index>=len(keys)-2 else 16) or b in seen:raise ValueError('Keys must be independent')
            seen.add(b)
    return value

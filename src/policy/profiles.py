"""Capabilities, not an arbitrary ranking of algorithm names."""
from dataclasses import dataclass, asdict

ASCON='ascon-aead128-v1'

@dataclass(frozen=True)
class Profile:
    profile_id: str
    version: int
    algorithm: str
    status: str
    parameters: dict
    capabilities: tuple
    protocol: str
    activation_allowed: bool
    limitations: str

IMPLEMENTED={ASCON:Profile(ASCON,1,'Ascon-AEAD128','implemented',
    {'key_bytes':16,'nonce_bytes':16,'tag_bytes':16},('mqtt_tls','aead','telemetry_v2'),
    'MQTT telemetry v2',True,'Reference implementation; independent full verification not claimed')}


def registry():return [asdict(p) for p in IMPLEMENTED.values()]


def recommend(profile_id,capabilities,minimum=ASCON,*,simulation=False):
    profiles=dict(IMPLEMENTED)
    if simulation:
        profiles['simulated-profile']=Profile('simulated-profile',1,'SIMULATED','experimental',{},
            ('mqtt_tls','aead','telemetry_v2'),'SIMULATION ONLY',False,'No implemented primitive')
    p=profiles.get(profile_id)
    if p is None:return {'profile_id':profile_id,'status':'unsupported_profile','applicable':False}
    if minimum!=ASCON or not set(IMPLEMENTED[ASCON].capabilities)<=set(capabilities):
        return {'profile_id':profile_id,'status':'minimum_protection_violation','applicable':False}
    if not set(p.capabilities)<=set(capabilities):return {'profile_id':profile_id,'status':'unsupported_profile','applicable':False}
    return {'profile_id':profile_id,'status':'simulated' if profile_id=='simulated-profile' else 'recommended',
            'applicable':False,'reason':'No live control channel or authenticated device acknowledgement'}

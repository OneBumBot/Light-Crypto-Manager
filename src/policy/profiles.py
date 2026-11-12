"""Capabilities, not an arbitrary ranking of algorithm names."""
from dataclasses import dataclass, asdict

ASCON='ascon-aead128-v1'
AES='aes-128-gcm-v1'

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
    server_implemented: bool = False
    device_implemented: bool = False
    known_vectors_passed: bool = False
    software_e2e_passed: bool = False
    device_implementations: tuple = ('python-device-agent-v1',)

IMPLEMENTED={ASCON:Profile(ASCON,1,'Ascon-AEAD128','implemented',
    {'key_bytes':16,'nonce_bytes':16,'tag_bytes':16},('mqtt_tls','aead','telemetry_v2'),
    'MQTT telemetry v2',True,'Python reference, no hardware/constant-time certification',server_implemented=True,device_implemented=True,known_vectors_passed=True,software_e2e_passed=True),
    AES:Profile(AES,1,'AES-128-GCM','verified',{'key_bytes':16,'nonce_bytes':12,'tag_bytes':16},
        ('mqtt_tls','aead','telemetry_v2'),'MQTT telemetry v2',True,'cryptography AESGCM; software agent verified, ARM unmeasured',server_implemented=True,device_implemented=True,known_vectors_passed=True,software_e2e_passed=True)}


def registry():
    from src.crypto_profiles import PROFILES
    return [dict(asdict(p),implementation_status=p.status,cryptographic_validation_status='published_vectors_verified' if p.known_vectors_passed else 'unverified',lab_eligibility=p.activation_allowed,production_eligibility='not_assessed' if p.profile_id!= 'kuznyechik-mgm-v1' else 'not_approved',implementation_backends=['go-one-shot-v1','go-bounded-worker-v1'] if p.profile_id=='kuznyechik-mgm-v1' else ['python-reference-v1'] if p.profile_id==ASCON else ['cryptography-native-v1'],key_lifetime_requirements='durable per-key invocation/block/verification budget; reviewed rekey on exhaustion' if p.profile_id=='kuznyechik-mgm-v1' else 'existing nonce/epoch policy',
        aead_mode='MGM' if p.profile_id=='kuznyechik-mgm-v1' else 'GCM' if p.profile_id==AES else 'Ascon-AEAD128',
        key_bytes=PROFILES[p.profile_id]['key_bytes'],nonce_bytes=PROFILES[p.profile_id]['nonce_bytes'],tag_bytes=PROFILES[p.profile_id]['tag_bytes'],
        nonce_policy=p.parameters.get('nonce_policy','existing-v1'),usage_limits=p.parameters.get('usage_limits',{})) for p in IMPLEMENTED.values()]


def recommend(profile_id,capabilities,minimum=ASCON,*,simulation=False):
    profiles=dict(IMPLEMENTED)
    if simulation:
        profiles['simulated-profile']=Profile('simulated-profile',1,'SIMULATED','experimental',{},
            ('mqtt_tls','aead','telemetry_v2'),'SIMULATION ONLY',False,'No implemented primitive')
    p=profiles.get(profile_id)
    if p is None:return {'profile_id':profile_id,'status':'unsupported_profile','applicable':False}
    if minimum not in IMPLEMENTED or not set(IMPLEMENTED[ASCON].capabilities)<=set(capabilities):
        return {'profile_id':profile_id,'status':'minimum_protection_violation','applicable':False}
    if not set(p.capabilities)<=set(capabilities):return {'profile_id':profile_id,'status':'unsupported_profile','applicable':False}
    return {'profile_id':profile_id,'status':'simulated' if profile_id=='simulated-profile' else 'recommended',
            'applicable':False,'reason':'Policy stays DRY_RUN; live control requires separate manual administrative authorization'}

# Explicit lab validation only. Ordinary deployments retain the two released profiles.
from src.kuz_release import validation_enabled
if validation_enabled():
    KUZ='kuznyechik-mgm-v1'
    IMPLEMENTED[KUZ]=Profile(KUZ,1,'Kuznyechik-MGM','software_e2e_verified',
        {'key_bytes':32,'nonce_bytes':16,'tag_bytes':16,'aead_mode':'MGM',
         'nonce_policy':'epoch31-sequence64-LCM01','usage_limits':{'reserved_invocations':1048576,'blocks_per_invocation':320,'verify_attempts':1048576}},
        ('mqtt_tls','aead','telemetry_v2'),'MQTT telemetry v2',True,
        'Explicit isolated software validation; timing resistance and ARM not verified; no certification',
        server_implemented=True,device_implemented=True,known_vectors_passed=True,software_e2e_passed=True)

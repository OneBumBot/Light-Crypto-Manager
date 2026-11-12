"""Explicit telemetry AEAD dispatch. No fallback, probing or strength ranking."""
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from src.web.ascon.ascon import ascon_encrypt, ascon_decrypt
from src.kuz_release import validation_enabled

ASCON = 'ascon-aead128-v1'
AES = 'aes-128-gcm-v1'
KUZ = 'kuznyechik-mgm-v1'
PROFILES = {
    ASCON: dict(algorithm='Ascon-AEAD128', key_bytes=16, nonce_bytes=16, tag_bytes=16),
    AES: dict(algorithm='AES-128-GCM', key_bytes=16, nonce_bytes=12, tag_bytes=16),
    KUZ: dict(algorithm='Kuznyechik-MGM', key_bytes=32, nonce_bytes=16, tag_bytes=16,
              aead_mode='MGM',version=1,protocol_version=2,nonce_policy='epoch31-sequence64-LCM01',
              usage_limits=dict(reserved_invocations=1048576,blocks_per_invocation=320,verify_attempts=1048576),
              implementation_status='software_e2e_verified',activation_allowed=validation_enabled()),
}
BY_ALGORITHM = {v['algorithm']: k for k,v in PROFILES.items()}



def _ascon_encrypt(key, nonce, ad, plaintext):
    return ascon_encrypt(key, nonce, ad, plaintext, 'Ascon-AEAD128')


def _ascon_decrypt(key, nonce, ad, ciphertext):
    value = ascon_decrypt(key, nonce, ad, ciphertext, 'Ascon-AEAD128')
    if value is None:
        raise ValueError('AEAD authentication failed')
    return value


from src import kuz_provider

PROVIDERS = {
    KUZ: (kuz_provider.encrypt, kuz_provider.decrypt),
    ASCON: (_ascon_encrypt, _ascon_decrypt),
    AES: (lambda k,n,a,p: AESGCM(k).encrypt(n,p,a),
          lambda k,n,a,c: AESGCM(k).decrypt(n,c,a)),
}


def validate_dispatch():
    if set(PROVIDERS) != set(PROFILES):
        raise RuntimeError('Missing or unexpected crypto provider')
    names = [p['algorithm'] for p in PROFILES.values()]
    if len(names) != len(set(names)):
        raise RuntimeError('Duplicate wire algorithm')


validate_dispatch()


def _parameters(profile, key, nonce, ad, data):
    if type(profile) is not str or profile not in PROFILES or profile not in PROVIDERS:
        raise ValueError('Unknown AEAD profile')
    if any(type(v) is not bytes for v in (key,nonce,ad,data)):
        raise ValueError('AEAD inputs must be bytes')
    p = PROFILES[profile]
    if len(key)!=p['key_bytes'] or len(nonce)!=p['nonce_bytes']:
        raise ValueError('Invalid AEAD parameters')
    return p


def encrypt(profile, key, nonce, ad, plaintext):
    _parameters(profile,key,nonce,ad,plaintext)
    return PROVIDERS[profile][0](key,nonce,ad,plaintext)


def decrypt(profile, key, nonce, ad, ciphertext):
    p=_parameters(profile,key,nonce,ad,ciphertext)
    if len(ciphertext)<p['tag_bytes']:
        raise ValueError('Invalid AEAD parameters')
    return PROVIDERS[profile][1](key,nonce,ad,ciphertext)

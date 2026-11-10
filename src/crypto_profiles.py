"""Explicit telemetry AEAD dispatch. No fallback, probing or strength ranking."""
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from src.web.ascon.ascon import ascon_encrypt, ascon_decrypt

ASCON = 'ascon-aead128-v1'
AES = 'aes-128-gcm-v1'
PROFILES = {
    ASCON: dict(algorithm='Ascon-AEAD128', key_bytes=16, nonce_bytes=16, tag_bytes=16),
    AES: dict(algorithm='AES-128-GCM', key_bytes=16, nonce_bytes=12, tag_bytes=16),
}
BY_ALGORITHM = {v['algorithm']: k for k,v in PROFILES.items()}


def encrypt(profile, key, nonce, ad, plaintext):
    p = PROFILES[profile]
    if len(key)!=p['key_bytes'] or len(nonce)!=p['nonce_bytes']:
        raise ValueError('Invalid AEAD parameters')
    if profile == AES:
        return AESGCM(key).encrypt(nonce, plaintext, ad)
    return ascon_encrypt(key, nonce, ad, plaintext, p['algorithm'])


def decrypt(profile, key, nonce, ad, ciphertext):
    p = PROFILES[profile]
    if len(key)!=p['key_bytes'] or len(nonce)!=p['nonce_bytes'] or len(ciphertext)<16:
        raise ValueError('Invalid AEAD parameters')
    if profile == AES:
        return AESGCM(key).decrypt(nonce, ciphertext, ad)
    value = ascon_decrypt(key, nonce, ad, ciphertext, p['algorithm'])
    if value is None:
        raise ValueError('AEAD authentication failed')
    return value

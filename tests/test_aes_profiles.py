"""NIST CAVP AES-GCM KAT, independent expected bytes; not roundtrip-only."""
import base64
from datetime import datetime,timezone
import pytest
from cryptography.exceptions import InvalidTag
from src.crypto_profiles import AES, encrypt, decrypt
from src.telemetry import encode_packet,decode_packet,InvalidTelemetry,canonical

# NIST CAVP gcmEncryptExtIV128.rsp (also pyca/cryptography vectors).
@pytest.mark.parametrize('plaintext,expected',[
    ('','58e2fccefa7e3061367f1d57a4e7455a'),
    ('00'*16,'0388dace60b6a392f328c2b971b2fe78ab6e47d42cec13bdf53a67b21257bddf'),
])
def test_nist_gcm_kat(plaintext,expected):
    key=bytes(16);nonce=bytes(12);pt=bytes.fromhex(plaintext);ct=bytes.fromhex(expected)
    assert encrypt(AES,key,nonce,b'',pt)==ct
    assert decrypt(AES,key,nonce,b'',ct)==pt

@pytest.mark.parametrize('part',['ciphertext','tag','aad','key','nonce'])
def test_aes_rejects_modifications(part):
    key=bytes(16);nonce=bytes(12);ad=b'bound device';ct=encrypt(AES,key,nonce,ad,b'measurement')
    if part=='ciphertext':ct=bytes([ct[0]^1])+ct[1:]
    if part=='tag':ct=ct[:-1]+bytes([ct[-1]^1])
    if part=='aad':ad+=b'x'
    if part=='key':key=bytes([1])+key[1:]
    if part=='nonce':nonce=bytes([1])+nonce[1:]
    with pytest.raises(InvalidTag):decrypt(AES,key,nonce,ad,ct)

@pytest.mark.parametrize('key,nonce',[(bytes(15),bytes(12)),(bytes(16),bytes(11)),(bytes(32),bytes(12))])
def test_strict_aes_parameters(key,nonce):
    with pytest.raises(ValueError):encrypt(AES,key,nonce,b'',b'')


def test_aes_v2_dispatch_and_binding(registry):
    registry['raspb1']['telemetry_keys']={'AES-128-GCM':bytes(range(100,116)).hex()}
    sensor=dict(temperature=23,humidity=45,timestamp=datetime.now(timezone.utc).isoformat())
    old=encode_packet(sensor,registry,'raspb1',3)
    packet=encode_packet(sensor,registry,'raspb1',4,profile=AES)
    msg=decode_packet(packet,'iot/sensors/raspb1',registry)
    assert msg.profile=='AES-128-GCM' and msg.sensor==sensor
    assert decode_packet(old,'iot/sensors/raspb1',registry).profile=='Ascon-AEAD128'
    assert len(base64.b64decode(packet['nonce']))==12
    packet['profile']='Ascon-AEAD128'
    with pytest.raises(InvalidTelemetry):decode_packet(packet,'iot/sensors/raspb1',registry)

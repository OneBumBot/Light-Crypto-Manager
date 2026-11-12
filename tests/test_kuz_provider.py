"""Independent published byte values, not merely provider round trips."""
import pytest
from src.kuz_provider import encrypt,decrypt,operation,self_test

KEY=bytes.fromhex('8899aabbccddeeff0011223344556677fedcba98765432100123456789abcdef')
NONCE=bytes.fromhex('1122334455667700ffeeddccbbaa9988')
AAD=bytes.fromhex('0202020202020202010101010101010104040404040404040303030303030303ea0505050505050505')
PLAIN=bytes.fromhex('''
1122334455667700ffeeddccbbaa9988
00112233445566778899aabbcceeff0a
112233445566778899aabbcceeff0a00
2233445566778899aabbcceeff0a0011
aabbcc
''')
CIPHER=bytes.fromhex('a9757b8147956e9055b8a33de89f42fc8075d2212bf9fd5bd3f7069aadc16b39497ab15915a6ba85936b5d0ea9f6851cc60c14d4d3f883d0ab94420695c76deb2c7552')
TAG=bytes.fromhex('cf5d656f40c34f5c46e8bb0e29fcdb4c')


def test_rfc7801_block_known_answer():
    pt=NONCE;ct=bytes.fromhex('7f679d90bebc24305a468d42b9d4edcd')
    assert operation(3,KEY,b'\0'*16,b'',pt)==ct
    assert operation(4,KEY,b'\0'*16,b'',ct)==pt


def test_rfc9058_a11_exact_ciphertext_and_tag():
    assert encrypt(KEY,NONCE,AAD,PLAIN)==CIPHER+TAG
    assert decrypt(KEY,NONCE,AAD,CIPHER+TAG)==PLAIN


def test_rfc9058_a12_empty_plaintext():assert self_test()


@pytest.mark.parametrize('field',['key','nonce','aad','ciphertext','tag','short_tag','long_tag'])
def test_authentication_failure_returns_no_plaintext(field):
    key,nonce,aad,ct=KEY,NONCE,AAD,CIPHER+TAG
    def flip(v):return bytes([v[0]^1])+v[1:]
    if field=='key':key=flip(key)
    elif field=='nonce':nonce=flip(nonce)
    elif field=='aad':aad=flip(aad)
    elif field=='ciphertext':ct=flip(ct)
    elif field=='tag':ct=ct[:-1]+bytes([ct[-1]^1])
    elif field=='short_tag':ct=ct[:-1]
    else:ct+=b'\0'
    with pytest.raises(ValueError):decrypt(key,nonce,aad,ct)


@pytest.mark.parametrize('bad',[None,True,1,1.5,[],{},'key'])
def test_wrong_input_types(bad):
    with pytest.raises(ValueError):encrypt(bad,NONCE,AAD,PLAIN)


@pytest.mark.parametrize('length',[0,1,15,16,31,33,64])
def test_key_length(length):
    with pytest.raises(ValueError):encrypt(b'x'*length,NONCE,AAD,PLAIN)


@pytest.mark.parametrize('n',[b'',b'0'*15,b'0'*17,b'\x80'+b'0'*15])
def test_nonce_rejected(n):
    with pytest.raises(ValueError):encrypt(KEY,n,AAD,PLAIN)


def test_mgm_length_rules_and_partial_blocks():
    with pytest.raises(ValueError):encrypt(KEY,NONCE,b'',b'')
    with pytest.raises(ValueError):encrypt(KEY,NONCE,b'x'*1025,b'x')
    with pytest.raises(ValueError):encrypt(KEY,NONCE,b'x',b'x'*4097)
    for a,p in [(b'',b'x'),(b'a',b''),(b'a'*17,b'p'*31)]:assert decrypt(KEY,NONCE,a,encrypt(KEY,NONCE,a,p))==p


@pytest.mark.parametrize('field',['nonce','aad','plaintext'])
@pytest.mark.parametrize('bad',[None,True,False,1,1.5,[],{},'bytes'])
def test_all_provider_inputs_have_exact_byte_types(field,bad):
    values=dict(key=KEY,nonce=NONCE,aad=AAD,plaintext=PLAIN);values[field]=bad
    with pytest.raises(ValueError):encrypt(**values)


def test_provider_failure_is_not_an_invalid_tag(monkeypatch):
    from src.kuz_provider import ProviderUnavailable
    monkeypatch.setenv('LCM_KUZ_PROVIDER','/nonexistent/lcm-kuz-provider')
    with pytest.raises(ProviderUnavailable):encrypt(KEY,NONCE,AAD,PLAIN)

import pytest
from src.crypto_profiles import encrypt,decrypt,PROVIDERS,PROFILES,validate_dispatch

@pytest.mark.parametrize('value',[None,True,False,0,1,1.5,[],{},'unknown','Ascon-AEAD128'])
def test_unknown_never_reaches_ascon(value,monkeypatch):
    def bad(*args):raise AssertionError('Unexpected provider fallback')
    monkeypatch.setitem(PROVIDERS,'ascon-aead128-v1',(bad,bad))
    with pytest.raises(ValueError):encrypt(value,b'k'*16,b'n'*16,b'ad',b'p')
    with pytest.raises(ValueError):decrypt(value,b'k'*16,b'n'*16,b'ad',b'c'*32)


def test_registration_requires_complete_unique_mapping(monkeypatch):
    monkeypatch.setitem(PROFILES,'missing',dict(algorithm='unique'))
    with pytest.raises(RuntimeError,match='provider'):validate_dispatch()
    monkeypatch.setitem(PROVIDERS,'missing',(lambda *a:b'',lambda *a:b''))
    monkeypatch.setitem(PROFILES,'missing',dict(algorithm='AES-128-GCM'))
    with pytest.raises(RuntimeError,match='Duplicate'):validate_dispatch()


def test_legacy_ascon_dispatch_preserves_external_known_answer():
    from src.crypto_profiles import ASCON
    key=bytes(range(16));nonce=bytes(range(16,32))
    expected=bytes.fromhex('4F9C278211BEC9316BF68F46EE8B2EC6')
    assert encrypt(ASCON,key,nonce,b'',b'')==expected
    assert decrypt(ASCON,key,nonce,b'',expected)==b''

"""Public-vector-only Magma experiment; no live registry, keys or MQTT grants."""
import sys,argparse,json
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('--candidate',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():raise ValueError('Immutable report')
    sys.path.insert(0,str(Path(a.candidate).resolve()))
    from pygost.gost3412 import GOST3412Magma
    from pygost.mgm import MGM
    key=bytes.fromhex('ffeeddccbbaa99887766554433221100f0f1f2f3f4f5f6f7f8f9fafbfcfdfeff');block=GOST3412Magma(key)
    pt=bytes.fromhex('fedcba9876543210');expected=bytes.fromhex('4ee901e5c2d8ca3d')
    assert block.encrypt(pt)==expected and block.decrypt(expected)==pt
    nonce=bytes.fromhex('12def06b3c130a59');aad=bytes.fromhex('01010101010101010202020202020202030303030303030304040404040404040505050505050505ea')
    plain=bytes.fromhex('ffeeddccbbaa998811223344556677008899aabbcceeff0a001122334455667799aabbcceeff0a001122334455667788aabbcceeff0a00112233445566778899aabbcc')
    expected=bytes.fromhex('c795066c5f9ea03b85113342459185ae1f2e00d6bf2b785d940470b8bb9c8e7d9a5dd3731f7ddc70ec27cb0ace6fa57670f65c646abb75d547aa37c3bcb5c34e03bb9ca7928069aa10fd10')
    mode=MGM(block.encrypt,8,8);assert mode.seal(nonce,plain,aad)==expected and mode.open(nonce,expected,aad)==plain
    bad=expected[:-1]+bytes([expected[-1]^1])
    try:mode.open(nonce,bad,aad)
    except ValueError:pass
    else:raise AssertionError('Magma invalid tag emitted plaintext')
    key2=bytes.fromhex('99aabbccddeeff0011223344556677fedcba98765432100123456789abcdef88');mode2=MGM(GOST3412Magma(key2).encrypt,8,8)
    n2=bytes.fromhex('0077665544332211');p2=bytes.fromhex('22334455667700ff');c2=bytes.fromhex('6a95e1426b259d4e334ee270450bec9e')
    assert mode2.seal(n2,p2,b'')==c2 and mode2.open(n2,c2,b'')==p2
    a.output.write_text(json.dumps(dict(rfc8891_block=True,rfc9058_a2_example1=True,rfc9058_a2_example2=True,full_tag_bits=64,invalid_tag_no_plaintext=True,public_vector_key_only=True,activation_allowed=False,live_registered=False,verdict='NOT_SUITABLE_FOR_CONTINUOUS_TELEMETRY',exit_code=0),indent=2))

if __name__=='__main__':main()

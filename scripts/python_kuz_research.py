"""Strict research-only wrapper for a separately supplied GPL PyGOST checkout.
Not imported by live registry or images; no key/nonce data emitted in reports.
"""
import argparse,json,sys,re,hashlib,subprocess
from pathlib import Path


def load(path):
    sys.path.insert(0,str(Path(path).resolve()))
    from pygost.gost3412 import GOST3412Kuznechik
    from pygost.mgm import MGM
    return GOST3412Kuznechik,MGM


def operation(implementation,key,nonce,aad,data,decrypt=False):
    if any(type(v) is not bytes for v in [key,nonce,aad,data]):raise ValueError('Exact bytes required')
    if len(key)!=32 or len(nonce)!=16 or nonce[0]&128 or len(aad)>1024:raise ValueError('Parameters')
    plain_length=len(data)-(16 if decrypt else 0)
    if not 0<=plain_length<=4096 or len(aad)+plain_length==0:raise ValueError('Lengths')
    Cipher,MGM=implementation;mode=MGM(Cipher(key).encrypt,16,16)
    return mode.open(nonce,data,aad) if decrypt else mode.seal(nonce,data,aad)


def main():
    p=argparse.ArgumentParser();p.add_argument('--candidate',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():raise ValueError('Immutable report exists')
    implementation=load(a.candidate);sys.path.insert(0,str(Path('tests').resolve()))
    from test_kuz_provider import KEY,NONCE,AAD,PLAIN,CIPHER,TAG
    Cipher,MGM=implementation;block=Cipher(KEY)
    keys=re.findall(r'"([0-9a-f]{32})"',Path('third_party/go-gostcrypto/kuznyechik/lcm_rfc7801_test.go').read_text())
    assert [bytes(k).hex() for k in block.ks]==keys
    assert block.encrypt(NONCE).hex()=='7f679d90bebc24305a468d42b9d4edcd'
    assert block.decrypt(bytes.fromhex('7f679d90bebc24305a468d42b9d4edcd'))==NONCE
    assert operation(implementation,KEY,NONCE,AAD,PLAIN)==CIPHER+TAG
    assert operation(implementation,KEY,NONCE,AAD,CIPHER+TAG,True)==PLAIN
    k2=bytes.fromhex('99aabbccddeeff0011223344556677fedcba98765432100123456789abcdef88')
    assert operation(implementation,k2,NONCE,b'\1'*16,b'').hex()=='7901e9ea2085cd247ed249695f9f8a85'
    from src.kuz_provider import encrypt
    cases=0;negatives=0
    for size in [0,1,15,16,17,64,256,1024]:
        for alen in [0,1,16,17]:
            if size+alen==0:continue
            import secrets
            key=secrets.token_bytes(32);nonce=secrets.token_bytes(15)+b'\1';nonce=bytes([nonce[0]&127])+nonce[1:];ad=b'a'*alen;plain=b'p'*size
            ct=operation(implementation,key,nonce,ad,plain);assert ct==encrypt(key,nonce,ad,plain)
            assert operation(implementation,key,nonce,ad,ct,True)==plain
            for bad in [ct[:-1]+bytes([ct[-1]^1]),ct[:-1],ct+b'x']:
                try:operation(implementation,key,nonce,ad,bad,True)
                except ValueError:negatives+=1
                else:raise AssertionError('Bad tag released plaintext')
            cases+=1
    parameter_negatives=0
    def rejected(k,n,a,d,dec=True):
        nonlocal parameter_negatives
        try:operation(implementation,k,n,a,d,dec)
        except ValueError:parameter_negatives+=1
        else:raise AssertionError('Invalid crypto parameters accepted')
    rejected(bytes([KEY[0]^1])+KEY[1:],NONCE,AAD,CIPHER+TAG)
    rejected(KEY,bytes([NONCE[0]^1])+NONCE[1:],AAD,CIPHER+TAG)
    rejected(KEY,NONCE,AAD+b'x',CIPHER+TAG)
    for bad in [None,True,1,1.5,[],{},'bytes']:
        for i in range(4):
            values=[KEY,NONCE,AAD,PLAIN];values[i]=bad;rejected(*values,dec=False)
    for length in [0,16,31,33]:rejected(b'k'*length,NONCE,AAD,PLAIN,False)
    rejected(KEY,b'0'*15,AAD,PLAIN,False);rejected(KEY,b'\x80'+b'0'*15,AAD,PLAIN,False)
    rejected(KEY,NONCE,b'',b'',False);rejected(KEY,NONCE,b'a'*1025,b'p',False);rejected(KEY,NONCE,b'a',b'p'*4097,False)
    # Isolated raw upstream API defects: never used to admit telemetry.
    mode=MGM(block.encrypt,16,16)
    class Oversized:
        def __len__(self):return 2**61
    mode._validate_sizes(Oversized(),b'')  # violates RFC bit bound but raw API accepts
    tag=mode._auth(bytearray(NONCE),b'',b'')
    empty_accepted=mode.open(NONCE,tag,b'')==b''
    candidate=Path(a.candidate)
    report=dict(revision=subprocess.check_output(['git','-C',str(candidate),'rev-parse','HEAD'],text=True).strip(),license='GPL-3.0',version=(candidate/'VERSION').read_text().strip(),rfc7801_round_keys=10,rfc7801_block=True,rfc9058_a1_examples=2,crosscheck_cases=cases,invalid_tag_rejections=negatives,parameter_negatives=parameter_negatives,raw_api_length_unit_defect=True,raw_api_empty_plaintext_and_aad_accepted=empty_accepted,live_registered=False,activation_allowed=False,source_hashes={str(p.relative_to(candidate)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [candidate/'pygost/mgm.py',candidate/'pygost/gost3412.py']},exit_code=0)
    a.output.write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))

if __name__=='__main__':main()

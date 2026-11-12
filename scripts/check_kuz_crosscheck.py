"""Differential check against a separately supplied, independently built executable.

The independent GPL implementation is neither linked nor distributed with runtime.
No randomly generated key, nonce or plaintext is written to the report.
"""
import argparse
import hashlib
import json
import os
import secrets
from pathlib import Path
from src import kuz_provider


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--independent',type=Path,required=True)
    a=p.parse_args()
    primary=kuz_provider.binary_path()
    binaries=[primary,str(a.independent.resolve())]
    cases=0
    for size in [0,1,15,16,17,31,32,64,256,1024,4096]:
        for aad_size in [0,1,16,17,1024]:
            if size+aad_size==0:continue
            key=secrets.token_bytes(32)
            nonce=bytes([secrets.randbelow(128)])+secrets.token_bytes(15)
            aad=secrets.token_bytes(aad_size);plain=secrets.token_bytes(size)
            outputs=[]
            for binary in binaries:
                os.environ['LCM_KUZ_PROVIDER']=binary
                ct=kuz_provider.encrypt(key,nonce,aad,plain)
                assert kuz_provider.decrypt(key,nonce,aad,ct)==plain
                bad=ct[:-1]+bytes([ct[-1]^1])
                try:kuz_provider.decrypt(key,nonce,aad,bad)
                except ValueError:pass
                else:raise AssertionError('Provider emitted plaintext for invalid tag')
                outputs.append(ct)
            assert outputs[0]==outputs[1],(size,aad_size)
            cases+=1
    os.environ['LCM_KUZ_PROVIDER']=primary
    print(json.dumps(dict(cases=cases,matching_ciphertext_and_full_tag=cases,
                         invalid_tag_rejections=2*cases,exit_code=0,
                         binaries=[hashlib.sha256(Path(b).read_bytes()).hexdigest() for b in binaries])))

if __name__=='__main__':main()

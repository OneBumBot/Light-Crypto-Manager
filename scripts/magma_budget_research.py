"""Exact rational aggregate MGM bounds, no live Magma profile or key issuance."""
import json,math,argparse
from fractions import Fraction
from pathlib import Path
from src.telemetry import canonical


def bounds(q,blocks,attempts,keys):
    ca=Fraction(keys*3*((blocks+4)*q)**2,2**64)
    ia=keys*attempts*(Fraction(3*((blocks+4)*q+blocks+3)**2,2**64)+Fraction(2,2**64))
    return ca,ia


def calculate():
    aad=len(canonical(dict(device_id='alpha',topic='iot/sensors/alpha',key_epoch=1,sequence_number=1,schema_version=2,profile='Magma-MGM')))
    rows=[]
    for a,p in [(1024,4096),(aad,83)]:
        blocks=math.ceil(a/8)+math.ceil(p/8)
        for bits in [32,40,48]:
            for keys in [1,3,30,300]:
                for attempts in [16,1000]:
                    eps=Fraction(1,2**bits);maximum=0
                    for q in range(1,attempts+1):
                        ca,ia=bounds(q,blocks,attempts,keys)
                        if ca<=eps and ia<=eps:maximum=q
                        else:break
                    ca,ia=bounds(maximum,blocks,attempts,keys)
                    rows.append(dict(aad_bytes=a,plaintext_bytes=p,blocks_per_message=blocks,epsilon_bits=bits,independent_keys_including_epochs=keys,total_verification_attempts_per_key=attempts,max_invocations_meeting_both_bounds=maximum,ca_at_max=float(ca),union_ia_at_max=float(ia)))
    return dict(rfc='https://www.rfc-editor.org/rfc/rfc9058#section-6',n=64,tag_bits=64,real_aad_bytes=aad,rows=rows,
        verdict='NOT_SUITABLE_FOR_CONTINUOUS_TELEMETRY',activation_allowed=False,
        reasons=['Current grant10000 exceeds positive computed per-key budgets','No versioned short per-profile lease or secure rekey lifecycle exists','Nonce uniqueness alone does not address 64-bit block bounds'],
        nonce_design_only='epoch-specific independent key; 0|counter63BE, no truncation of global sequence',exit_code=0)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():raise ValueError('Immutable report exists')
 a.output.write_text(json.dumps(calculate(),indent=2))

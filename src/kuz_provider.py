"""Pinned Go MGM adapter over private one-shot pipes. Not a network crypto service."""
import os,struct,subprocess

class ProviderUnavailable(RuntimeError):
    pass


def binary_path():return os.environ.get('LCM_KUZ_PROVIDER','/usr/local/bin/lcm-kuz-mgm')


def operation(op,key,nonce,aad,data):
    if any(type(v) is not bytes for v in [key,nonce,aad,data]):raise ValueError('AEAD inputs must be bytes')
    if type(op) is not int or op not in [1,2,3,4] or len(key)!=32 or len(nonce)!=16 or len(aad)>1024:raise ValueError('Invalid provider parameters')
    if op in [1,2] and nonce[0]&128:raise ValueError('Invalid MGM ICN')
    if op==1 and (len(data)>4096 or len(aad)+len(data)==0):raise ValueError('Invalid MGM length')
    if op==2 and (not 16<=len(data)<=4112 or len(aad)+len(data)-16==0):raise ValueError('Invalid MGM length')
    if op in [3,4] and (len(data)!=16 or aad):raise ValueError('Invalid block input')
    request=b'LCMKUZ01'+bytes([op])+key+nonce+struct.pack('!II',len(aad),len(data))+aad+data
    backend=os.environ.get('LCM_KUZ_BACKEND','one-shot')
    if backend=='persistent':
        from src.kuz_worker import WORKER
        response=WORKER.exchange(request)
    elif backend!='one-shot':raise ProviderUnavailable('Unknown provider backend')
    else:
        response=_one_shot(request)
    try:return _response(op,data,response)
    except ProviderUnavailable:
        if backend=='persistent':WORKER.close()
        raise


def _one_shot(request):
    try:
        # No keys in argv/env/logs, no shell; a fresh instance per operation.
        result=subprocess.run([binary_path()],input=request,capture_output=True,timeout=5,env={'GOMAXPROCS':'1','GODEBUG':'madvdontneed=1'})
    except (OSError,subprocess.TimeoutExpired):raise ProviderUnavailable('Kuznyechik provider unavailable') from None
    if result.returncode or result.stderr:raise ProviderUnavailable('Kuznyechik provider failed')
    return result.stdout


def _response(op,data,response):
    if not 1<=len(response)<=4113:raise ProviderUnavailable('Kuznyechik provider response bounds')
    status=response[0]
    if status in [1,2] and len(response)==1:raise ValueError('MGM authentication/parameter rejection')
    if status!=0:raise ProviderUnavailable('Kuznyechik provider internal failure')
    output=response[1:];expected=len(data)+(16 if op==1 else -16 if op==2 else 0)
    if len(output)!=expected:raise ProviderUnavailable('Kuznyechik provider output bounds')
    return output


def encrypt(key,nonce,aad,plaintext):return operation(1,key,nonce,aad,plaintext)
def decrypt(key,nonce,aad,ciphertext):return operation(2,key,nonce,aad,ciphertext)


def self_test():
    key=bytes.fromhex('99aabbccddeeff0011223344556677fedcba98765432100123456789abcdef88')
    nonce=bytes.fromhex('1122334455667700ffeeddccbbaa9988')
    tag=bytes.fromhex('7901e9ea2085cd247ed249695f9f8a85')
    return encrypt(key,nonce,b'\x01'*16,b'')==tag and decrypt(key,nonce,b'\x01'*16,tag)==b''

"""Behavioral IPC faults, exact tag failures, process lifecycle and device separation."""
import os,struct,subprocess,sys,time,secrets
from concurrent.futures import ThreadPoolExecutor
import pytest
from src.kuz_provider import encrypt,decrypt,ProviderUnavailable,binary_path
from src.kuz_worker import WORKER

@pytest.fixture(autouse=True)
def worker(monkeypatch):
    WORKER.close();monkeypatch.setenv('LCM_KUZ_BACKEND','persistent')
    yield
    WORKER.close()


def test_concurrent_distinct_keys_do_not_mix_responses():
    def device(i):
        key=secrets.token_bytes(32);ad=('device-'+str(i)).encode()
        for seq in range(1,21):
            nonce=seq.to_bytes(16,'big');plain=ad+bytes([seq])*17
            assert decrypt(key,nonce,ad,encrypt(key,nonce,ad,plain))==plain
    with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(device,range(4)))


def test_rotation_and_crash_never_retries_same_operation():
    key=secrets.token_bytes(32)
    encrypt(key,b'\0'*16,b'a',b'p');first=WORKER.process.pid
    WORKER.count=256
    encrypt(key,b'\0'*15+b'\1',b'a',b'p');assert WORKER.process.pid!=first
    WORKER.process.kill();WORKER.process.wait()
    with pytest.raises(ProviderUnavailable):encrypt(key,b'\0'*15+b'\2',b'a',b'p')
    assert WORKER.process is None
    assert decrypt(key,b'\0'*15+b'\3',b'a',encrypt(key,b'\0'*15+b'\3',b'a',b'p'))==b'p'


@pytest.mark.parametrize('fault',['wrong_id','truncated','oversized','unexpected_status','plaintext_on_error','timeout'])
def test_malformed_worker_never_returns_plaintext(tmp_path,monkeypatch,fault):
    path=tmp_path/'fake-worker'
    action={
        'wrong_id':"out=(999).to_bytes(8,'big')+b'\\0'+b'x'*17",
        'truncated':"out=identity+b'\\0';os.write(1,(30).to_bytes(4,'big')+out);sys.exit(0)",
        'oversized':"os.write(1,(999999).to_bytes(4,'big'));sys.exit(0)",
        'unexpected_status':"out=identity+b'\\7'",
        'plaintext_on_error':"out=identity+b'\\1plaintext must not escape'",
        'timeout':"time.sleep(8);out=identity+b'\\0'",
    }[fault]
    path.write_text('#!'+sys.executable+'\nimport sys,os,time\nn=int.from_bytes(sys.stdin.buffer.read(4),"big")\nr=sys.stdin.buffer.read(n);identity=r[:8]\n'+action+'\nos.write(1,len(out).to_bytes(4,"big")+out)\n')
    path.chmod(0o700);monkeypatch.setenv('LCM_KUZ_PROVIDER',str(path));started=time.monotonic()
    with pytest.raises(ProviderUnavailable):encrypt(b'k'*32,b'\0'*16,b'a',b'p')
    assert time.monotonic()-started<7
    assert WORKER.process is None


def test_bad_tag_returns_no_plaintext_and_worker_remains_usable():
    key=secrets.token_bytes(32);nonce=b'\0'*16
    ct=encrypt(key,nonce,b'a',b'p');pid=WORKER.process.pid
    with pytest.raises(ValueError):decrypt(key,nonce,b'a',ct[:-1]+bytes([ct[-1]^1]))
    assert WORKER.process.pid==pid and decrypt(key,nonce,b'a',ct)==b'p'


def test_native_partial_frame_and_duplicate_request_id():
    request=b'LCMKUZ01'+b'\1'+b'k'*32+b'\0'*16+struct.pack('!II',1,1)+b'a'+b'p'
    frame=struct.pack('!I',8+len(request))+struct.pack('!Q',1)+request
    r=subprocess.run([binary_path(),'--worker'],input=frame+frame,capture_output=True,timeout=5)
    assert r.returncode==0 and not r.stderr
    length=struct.unpack('!I',r.stdout[:4])[0];assert len(r.stdout)==4+length
    assert r.stdout[4:12]==struct.pack('!Q',1)
    r=subprocess.run([binary_path(),'--worker'],input=struct.pack('!I',99999999),capture_output=True,timeout=5)
    assert r.stdout==b''
    r=subprocess.run([binary_path(),'--worker'],input=frame[:-1],capture_output=True,timeout=5)
    assert r.stdout==b''


def test_native_request_budget_is_enforced():
    key=secrets.token_bytes(32);frames=[]
    for i in range(1,258):
        request=b'LCMKUZ01'+b'\1'+key+i.to_bytes(16,'big')+struct.pack('!II',1,1)+b'a'+b'p'
        frames.append(struct.pack('!I',8+len(request))+struct.pack('!Q',i)+request)
    r=subprocess.run([binary_path(),'--worker'],input=b''.join(frames),capture_output=True,timeout=5)
    data=r.stdout;ids=[]
    while data:
        length=struct.unpack('!I',data[:4])[0];ids.append(struct.unpack('!Q',data[4:12])[0]);data=data[4+length:]
    assert ids==list(range(1,257)) and r.returncode==0


def test_forked_child_cannot_use_or_kill_parent_worker():
    key=secrets.token_bytes(32);encrypt(key,b'\0'*16,b'a',b'p');parent=WORKER.process.pid
    child=os.fork()
    if child==0:
        try:
            assert encrypt(secrets.token_bytes(32),b'\0'*16,b'a',b'p');WORKER.close();os._exit(0)
        except BaseException:os._exit(1)
    _,status=os.waitpid(child,0);assert os.waitstatus_to_exitcode(status)==0
    assert WORKER.process.pid==parent and WORKER.process.poll() is None
    assert encrypt(key,b'\0'*15+b'\1',b'a',b'p')


def test_dispatch_missing_backend_never_falls_back(monkeypatch):
    from src.crypto_profiles import KUZ,encrypt as dispatch
    monkeypatch.setenv('LCM_KUZ_PROVIDER','/nonexistent/mgm-backend')
    with pytest.raises(ProviderUnavailable):dispatch(KUZ,b'k'*32,b'\0'*16,b'a',b'p')


def test_stderr_eof_does_not_discard_complete_valid_response(tmp_path,monkeypatch):
    path=tmp_path/'eof-worker'
    path.write_text('#!'+sys.executable+'\nimport sys,os\nn=int.from_bytes(sys.stdin.buffer.read(4),"big");r=sys.stdin.buffer.read(n)\nos.close(2)\nout=r[:8]+b"\\0"+b"x"*17\nos.write(1,len(out).to_bytes(4,"big")+out)\n')
    path.chmod(0o700);monkeypatch.setenv('LCM_KUZ_PROVIDER',str(path))
    assert encrypt(b'k'*32,b'\0'*16,b'a',b'p')==b'x'*17

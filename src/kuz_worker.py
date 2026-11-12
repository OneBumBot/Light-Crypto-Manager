"""Bounded local IPC, serialized per process. Never retries a failed operation."""
import atexit,os,selectors,struct,subprocess,threading,time
from src.kuz_provider import ProviderUnavailable,binary_path

class Worker:
    def __init__(self):
        self.lock=threading.Lock();self.process=None;self.owner=os.getpid();self.count=0;self.started=0;self.path=None
    def _stop(self):
        p=self.process;self.process=None
        if p is None:return
        if self.owner==os.getpid():
            if p.poll() is None:p.kill()
            p.wait(timeout=1)
        for f in [p.stdin,p.stdout,p.stderr]:f.close()
    def close(self):
        with self.lock:self._stop()
    def _io(self,fd,amount,deadline,write=None):
        result=bytearray();offset=0
        with selectors.DefaultSelector() as selector:
            selector.register(fd,selectors.EVENT_WRITE if write is not None else selectors.EVENT_READ)
            selector.register(self.process.stderr,selectors.EVENT_READ)
            while offset<amount:
                remaining=deadline-time.monotonic()
                if remaining<=0:raise ProviderUnavailable('Provider IPC timeout')
                for key,_ in selector.select(remaining):
                    if key.fileobj is self.process.stderr:
                        try:noise=os.read(self.process.stderr.fileno(),1)
                        except BlockingIOError:continue
                        if noise:raise ProviderUnavailable('Provider stderr output')
                        selector.unregister(self.process.stderr) # EOF may race a complete stdout response
                        continue
                    try:
                        if write is not None:
                            n=os.write(fd,write[offset:]);offset+=n
                        else:
                            b=os.read(fd,amount-offset)
                            if not b:raise ProviderUnavailable('Truncated provider response')
                            result.extend(b);offset+=len(b)
                    except BlockingIOError:continue
        return bytes(result)
    def exchange(self,request):
        deadline=time.monotonic()+5
        if not self.lock.acquire(timeout=5):raise ProviderUnavailable('Provider busy timeout')
        try:
            if self.owner!=os.getpid():
                # Inherited pipes must not be used, nor may a forked child kill the parent's worker.
                self._stop();self.owner=os.getpid()
            if self.process is not None and (self.count>=256 or time.monotonic()-self.started>=25 or self.path!=binary_path()):self._stop()
            if self.process is None:
                self.path=binary_path()
                self.process=subprocess.Popen([self.path,'--worker'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0,
                    env={'GOMAXPROCS':'1','GOMEMLIMIT':'32MiB','GODEBUG':'madvdontneed=1'})
                for f in [self.process.stdin,self.process.stdout,self.process.stderr]:os.set_blocking(f.fileno(),False)
                self.count=0;self.started=time.monotonic()
            # If the previous process crashed, fail this call; create a fresh one only on the next call.
            if self.process.poll() is not None:raise ProviderUnavailable('Provider process exited')
            self.count+=1;identity=struct.pack('!Q',self.count);frame=identity+request
            self._io(self.process.stdin.fileno(),len(frame)+4,deadline,struct.pack('!I',len(frame))+frame)
            length=struct.unpack('!I',self._io(self.process.stdout.fileno(),4,deadline))[0]
            if not 9<=length<=4121:raise ProviderUnavailable('Provider response bounds')
            response=self._io(self.process.stdout.fileno(),length,deadline)
            if response[:8]!=identity:raise ProviderUnavailable('Provider request binding')
            return response[8:]
        except (OSError,subprocess.SubprocessError,ProviderUnavailable):
            self._stop();raise ProviderUnavailable('Persistent provider operation failed') from None
        finally:self.lock.release()

WORKER=Worker()
def _after_fork():
    WORKER._stop()  # owner PID differs: close inherited pipes, never signal parent worker
    WORKER.owner=os.getpid();WORKER.lock=threading.Lock()
if hasattr(os,'register_at_fork'):os.register_at_fork(after_in_child=_after_fork)
atexit.register(WORKER.close)

"""Exact byte matching via GNU grep's byte fixed-string matcher; never prints patterns."""
import subprocess,tempfile,os
from pathlib import Path


class SecretMatcher:
 def __init__(self,needles):
  needles=set(needles);self.extra=[v for v in needles if b'\n' in v or b'\r' in v];regular=needles-set(self.extra)
  self.file=tempfile.TemporaryFile();self.path=Path('/proc/self/fd/'+str(self.file.fileno()))
  try:self.file.write(b'\n'.join(regular));self.file.flush()
  except BaseException:self.file.close();raise
  self.regular=bool(regular)
 def contains(self,data):
  if any(v in data for v in self.extra):return True
  if not self.regular:return False
  self.file.seek(0)
  r=subprocess.run(['grep','--binary-files=text','--fixed-strings','--quiet','--file',str(self.path),'-'],env=dict(os.environ,LC_ALL='C'),pass_fds=(self.file.fileno(),),input=data,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=60)
  if r.returncode not in [0,1]:raise RuntimeError('Private fixed-string scan failed; no patterns emitted')
  return r.returncode==0
 def close(self):self.file.close()
 def __enter__(self):return self
 def __exit__(self,*args):self.close()

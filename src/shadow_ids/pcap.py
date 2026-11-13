"""Streaming classic PCAP reader with explicit EOF/truncation; no whole-stream buffering."""
import struct
MAGIC={b'\xd4\xc3\xb2\xa1':('<',1000000),b'\xa1\xb2\xc3\xd4':('>',1000000),b'\x4d\x3c\xb2\xa1':('<',1000000000),b'\xa1\xb2\x3c\x4d':('>',1000000000)}
def exact(stream,n):
 out=bytearray()
 while len(out)<n:
  value=stream.read(n-len(out))
  if not value:raise ValueError('Truncated PCAP stream')
  out.extend(value)
 return bytes(out)
def header(stream):
 raw=exact(stream,24)
 if raw[:4] not in MAGIC:raise ValueError('Unsupported capture format')
 endian,scale=MAGIC[raw[:4]];major,minor,_,_,snap,link=struct.unpack(endian+'HHIIII',raw[4:])
 if (major,minor)!=(2,4) or link!=1 or not 54<=snap<=1048576:raise ValueError('Unsupported PCAP linktype')
 return raw,endian,scale,snap
def record(stream,endian,scale,snap):
 first=stream.read(1)
 if not first:return None
 head=first+exact(stream,15);sec,frac,inc,orig=struct.unpack(endian+'IIII',head)
 if frac>=scale or not 0<inc<=min(snap,65535):raise ValueError('Invalid PCAP record')
 raw=exact(stream,inc)
 return head,raw,orig,sec+frac/scale
